"""End-to-end ingestion run with fake external systems.

Oracle (station list), the stationboard API and the storage are replaced:
the run writes real Parquet files into a temporary folder, which are then read back.
"""
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest

from ingestion import run
from ingestion.api import FetchError
from ingestion.storage import LocalStorage
from ingestion.transform import DEPARTURES_SCHEMA, INGESTION_LOG_SCHEMA

STATIONS = [
    {"station_id": "8504300", "station_name": "Biel/Bienne"},
    {"station_id": "8507000", "station_name": "Bern"},
    {"station_id": "8503000", "station_name": "Zürich HB"},
    {"station_id": "8504221", "station_name": "Neuchâtel"},
]
LIST_AS_OF = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)


def departure(station_id, minute, delay=None):
    """Minimal stationboard entry, shaped like the API response."""
    return {
        "category": "IC",
        "number": "5",
        "operator": "SBB",
        "to": "Genève-Aéroport",
        "stop": {
            "station": {"id": station_id},
            "departureTimestamp": 1793001600 + 60 * minute,
            "departure": "2026-10-26T09:00:00+0100",
            "delay": delay,
            "platform": "3",
        },
    }


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def fake_run(monkeypatch, storage):
    """Configure a run: `failing` lists the station ids whose API call fails."""

    def configure(failing=()):
        def fake_fetch(station_id, session=None):
            if station_id in failing:
                raise FetchError("HTTP 503 after 3 attempts", 3)
            return [departure(station_id, 0, delay=2), departure(station_id, 5)], 1

        monkeypatch.setattr(run, "get_storage", lambda: storage)
        monkeypatch.setattr(run, "load_stations", lambda s: (STATIONS, "oracle:cloud", LIST_AS_OF))
        monkeypatch.setattr(run, "fetch_stationboard", fake_fetch)
        monkeypatch.setattr(run, "PAUSE_BETWEEN_STATIONS_S", 0)

    return configure


def read_dataset(storage, dataset):
    files = sorted((storage.root / "bronze" / dataset).rglob("*.parquet"))
    assert len(files) == 1, f"expected one batch file in {dataset}, found {len(files)}"
    return files[0], pq.read_table(files[0])


def test_successful_run_writes_departures_and_log(fake_run, storage):
    fake_run()

    assert run.main() == 0

    departures_file, departures = read_dataset(storage, "transport_stationboard")
    _, log = read_dataset(storage, "_ingestion_log")

    assert departures_file.parent.name.startswith("ingestion_date=")
    assert departures.schema.equals(DEPARTURES_SCHEMA)
    assert log.schema.equals(INGESTION_LOG_SCHEMA)
    assert departures.num_rows == 2 * len(STATIONS)

    log_rows = log.to_pylist()
    assert [r["status"] for r in log_rows] == ["success"] * len(STATIONS)
    assert {r["station_source"] for r in log_rows} == {"oracle:cloud"}
    assert {r["station_list_as_of"] for r in log_rows} == {LIST_AS_OF}
    # every departure row belongs to the run recorded in the log
    assert set(departures.column("_batch_id").to_pylist()) == {log_rows[0]["_batch_id"]}


def test_one_failed_station_is_logged_and_the_run_succeeds(fake_run, storage):
    fake_run(failing={"8507000"})

    assert run.main() == 0

    _, log = read_dataset(storage, "_ingestion_log")
    failed = [r for r in log.to_pylist() if r["status"] == "failed"]
    assert [r["station_id"] for r in failed] == ["8507000"]
    assert failed[0]["error"] == "HTTP 503 after 3 attempts"
    assert failed[0]["attempts"] == 3


def test_half_of_the_stations_failing_does_not_fail_the_run(fake_run):
    fake_run(failing={"8504300", "8507000"})          # 2 of 4 = 50 %, threshold not exceeded

    assert run.main() == 0


def test_more_than_half_failing_fails_the_run_but_keeps_the_log(fake_run, storage):
    fake_run(failing={"8504300", "8507000", "8503000"})   # 3 of 4

    assert run.main() == 1

    _, log = read_dataset(storage, "_ingestion_log")
    assert [r["status"] for r in log.to_pylist()].count("failed") == 3


def test_all_stations_failing_still_writes_the_log(fake_run, storage):
    fake_run(failing={s["station_id"] for s in STATIONS})

    assert run.main() == 1

    assert not (storage.root / "bronze" / "transport_stationboard").exists()
    _, log = read_dataset(storage, "_ingestion_log")
    assert log.num_rows == len(STATIONS)
