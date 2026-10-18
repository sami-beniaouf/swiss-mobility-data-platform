"""Hourly ingestion run.

    python -m ingestion.run

1. Load the station list (Oracle, cache fallback).
2. Fetch the stationboard of every station; one failure does not stop the others.
3. Write the departures and the ingestion log (one row per station) to bronze.
4. Exit with code 1 when more than MAX_FAILURE_RATIO of the stations failed,
   so that the scheduler marks the run as failed and raises an alert.
"""
import logging
import sys
import time
from datetime import datetime, timezone

import requests

from ingestion.api import FetchError, fetch_stationboard
from ingestion.config import (
    BRONZE_DEPARTURES_DIR,
    BRONZE_LOG_DIR,
    MAX_FAILURE_RATIO,
    PAUSE_BETWEEN_STATIONS_S,
)
from ingestion.stations import load_stations
from ingestion.storage import write_batch
from ingestion.transform import DEPARTURES_SCHEMA, INGESTION_LOG_SCHEMA, to_row

log = logging.getLogger("ingestion")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    run_started = datetime.now(timezone.utc).replace(microsecond=0)
    batch_id = run_started.strftime("%Y%m%dT%H%M%SZ")
    ingestion_date = run_started.strftime("%Y-%m-%d")
    log.info("Run %s started", batch_id)

    try:
        stations, station_source = load_stations()
    except KeyError as exc:
        log.error("Run %s aborted: missing environment variable %s", batch_id, exc)
        return 1
    except (ValueError, RuntimeError) as exc:
        log.error("Run %s aborted: %s", batch_id, exc)
        return 1

    departure_rows, log_rows = [], []
    with requests.Session() as session:
        session.headers["User-Agent"] = "swiss-mobility-data-platform/ingestion"

        for i, station in enumerate(stations):
            station_id, station_name = station["station_id"], station["station_name"]
            started = datetime.now(timezone.utc)
            entry = {
                "_batch_id": batch_id,
                "station_id": station_id,
                "station_name": station_name,
                "station_source": station_source,
                "started_at": started,
            }
            try:
                departures, attempts = fetch_stationboard(station_id, session=session)
                rows = [to_row(dep, run_started, batch_id) for dep in departures]
                departure_rows.extend(rows)
                entry.update(status="success", rows=len(rows), attempts=attempts, error=None)
                log.info("[%s %s] %d departures (%d attempt(s))", station_id, station_name, len(rows), attempts)
            except FetchError as exc:
                entry.update(status="failed", rows=0, attempts=exc.attempts, error=str(exc))
                log.error("[%s %s] failed: %s", station_id, station_name, exc)
            except Exception as exc:          # unexpected data shape: record it, keep the other stations
                entry.update(status="failed", rows=0, attempts=None, error=f"{type(exc).__name__}: {exc}")
                log.exception("[%s %s] unexpected error", station_id, station_name)

            entry["finished_at"] = datetime.now(timezone.utc)
            log_rows.append(entry)

            if i < len(stations) - 1:
                time.sleep(PAUSE_BETWEEN_STATIONS_S)

    # The ingestion log is written in every case: it is the only trace of a run where all stations failed.
    if departure_rows:
        path = write_batch(departure_rows, DEPARTURES_SCHEMA, BRONZE_DEPARTURES_DIR, ingestion_date, batch_id)
        log.info("Wrote %d departures to %s", len(departure_rows), path)
    log_path = write_batch(log_rows, INGESTION_LOG_SCHEMA, BRONZE_LOG_DIR, ingestion_date, batch_id)

    failed = sum(1 for r in log_rows if r["status"] == "failed")
    log.info("Run %s finished: %d/%d stations ok, %d failed. Log: %s",
             batch_id, len(stations) - failed, len(stations), failed, log_path)

    if failed > len(stations) * MAX_FAILURE_RATIO:
        log.error("Run %s failed: %d/%d stations failed (threshold %.0f%%)",
                  batch_id, failed, len(stations), MAX_FAILURE_RATIO * 100)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
