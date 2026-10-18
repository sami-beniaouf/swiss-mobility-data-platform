"""Station list: read from the Oracle data hub, with a local cache as fallback.

Oracle is the single source of truth for the stations (also used by dim_station in dbt).
Every valid list is cached so that the ingestion keeps running when Oracle is unavailable:
the departures API keeps no history, so a missed run is lost permanently.
Only a non-empty list may overwrite the cache.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import oracledb

from ingestion.config import STATIONS_CACHE_PATH

log = logging.getLogger(__name__)

STATION_QUERY = """
    SELECT station_id, station_name
    FROM stations
    ORDER BY station_id
"""


def _read_oracle(query, dsn, user, password):
    with oracledb.connect(user=user, password=password, dsn=dsn, tcp_connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [{"station_id": str(sid), "station_name": name} for sid, name in cur.fetchall()]


def _write_cache(stations, cache_path: Path):
    """Atomic write: a crash during the write never leaves a half-written cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "oracle:stations",
        "stations": stations,
    }
    tmp_path = cache_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, cache_path)


def _read_cache(cache_path: Path):
    if not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not payload.get("stations"):
        return None
    return payload["stations"], payload["cached_at"]


def load_stations(cache_path=STATIONS_CACHE_PATH, query=STATION_QUERY, dsn=None, user=None, password=None):
    """Return (stations, source), source being "oracle" or "cache".

    Raises RuntimeError when Oracle fails (or returns no station) and no cache is available.
    """
    dsn = dsn or os.environ["ORACLE_DSN"]
    user = user or os.environ["ORACLE_APP_USER"]
    password = password or os.environ["ORACLE_APP_PASSWORD"]

    try:
        stations = _read_oracle(query, dsn, user, password)
        if not stations:
            raise ValueError("Oracle returned 0 stations")
        _write_cache(stations, cache_path)
        log.info("Loaded %d stations from Oracle, cache refreshed", len(stations))
        return stations, "oracle"
    except (oracledb.Error, ValueError) as exc:
        oracle_error = f"{type(exc).__name__}: {exc}".splitlines()[0]

    cached = _read_cache(cache_path)
    if cached is None:
        raise RuntimeError(f"Station list unavailable: Oracle failed ({oracle_error}) and no cache at {cache_path}")

    stations, cached_at = cached
    log.warning("Oracle unavailable (%s). Using %d cached stations from %s", oracle_error, len(stations), cached_at)
    return stations, "cache"
