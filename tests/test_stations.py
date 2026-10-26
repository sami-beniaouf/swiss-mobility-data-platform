"""Station list: Oracle as the source, a cached copy as fallback."""
import json
from datetime import datetime, timezone

import oracledb
import pytest

from ingestion import stations
from ingestion.config import STATE_CONTAINER, STATIONS_CACHE_FILE
from ingestion.storage import LocalStorage

LOCAL = ("local", {})          # connection settings are irrelevant: Oracle is replaced
ORACLE_STATIONS = [
    {"station_id": "8504300", "station_name": "Biel/Bienne"},
    {"station_id": "8507000", "station_name": "Bern"},
]
CACHED_AT = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


def oracle_returns(rows):
    return lambda query, connect_kwargs: rows


def oracle_down(query, connect_kwargs):
    raise oracledb.OperationalError("DPY-6005: cannot connect to database")


def write_cache(storage, rows, cached_at=CACHED_AT):
    payload = {"cached_at": cached_at.isoformat(), "source": "oracle:local", "stations": rows}
    storage.write_bytes(STATE_CONTAINER, STATIONS_CACHE_FILE, json.dumps(payload).encode(), overwrite=True)


def read_cache(storage):
    return json.loads(storage.read_bytes(STATE_CONTAINER, STATIONS_CACHE_FILE))


class BrokenStorage(LocalStorage):
    """Storage whose reads or writes fail, like an unreachable or misconfigured account."""

    def __init__(self, root, fail_reads=False, fail_writes=False):
        super().__init__(root)
        self.fail_reads, self.fail_writes = fail_reads, fail_writes

    def write_bytes(self, *args, **kwargs):
        if self.fail_writes:
            raise OSError("The specified filesystem does not exist.")
        return super().write_bytes(*args, **kwargs)

    def read_bytes(self, *args, **kwargs):
        if self.fail_reads:
            raise OSError("Connection reset by peer")
        return super().read_bytes(*args, **kwargs)


def test_oracle_list_is_returned_and_cached(monkeypatch, storage):
    monkeypatch.setattr(stations, "_read_oracle", oracle_returns(ORACLE_STATIONS))

    result, source, as_of = stations.load_stations(storage, settings=LOCAL)

    assert (result, source) == (ORACLE_STATIONS, "oracle:local")
    cache = read_cache(storage)
    assert cache["stations"] == ORACLE_STATIONS
    assert datetime.fromisoformat(cache["cached_at"]) == as_of


def test_oracle_down_falls_back_to_the_cache(monkeypatch, storage):
    write_cache(storage, ORACLE_STATIONS)
    monkeypatch.setattr(stations, "_read_oracle", oracle_down)

    result, source, as_of = stations.load_stations(storage, settings=LOCAL)

    assert (result, source) == (ORACLE_STATIONS, "cache")
    assert as_of == CACHED_AT          # the age of the list is visible in the ingestion log


def test_empty_oracle_result_does_not_overwrite_the_cache(monkeypatch, storage):
    write_cache(storage, ORACLE_STATIONS)
    monkeypatch.setattr(stations, "_read_oracle", oracle_returns([]))

    result, source, _ = stations.load_stations(storage, settings=LOCAL)

    assert (result, source) == (ORACLE_STATIONS, "cache")
    assert read_cache(storage)["stations"] == ORACLE_STATIONS


def test_oracle_down_without_cache_aborts(monkeypatch, storage):
    monkeypatch.setattr(stations, "_read_oracle", oracle_down)

    with pytest.raises(RuntimeError, match="no cache"):
        stations.load_stations(storage, settings=LOCAL)


def test_cache_write_failure_keeps_the_oracle_list(monkeypatch, tmp_path):
    storage = BrokenStorage(tmp_path, fail_writes=True)
    monkeypatch.setattr(stations, "_read_oracle", oracle_returns(ORACLE_STATIONS))

    result, source, _ = stations.load_stations(storage, settings=LOCAL)

    assert (result, source) == (ORACLE_STATIONS, "oracle:local")


def test_unreadable_cache_with_oracle_down_aborts(monkeypatch, tmp_path):
    storage = BrokenStorage(tmp_path, fail_reads=True)
    monkeypatch.setattr(stations, "_read_oracle", oracle_down)

    with pytest.raises(RuntimeError, match="Station list unavailable"):
        stations.load_stations(storage, settings=LOCAL)


def test_invalid_oracle_target_is_rejected(monkeypatch):
    monkeypatch.setenv("ORACLE_TARGET", "alert-test")

    with pytest.raises(ValueError, match="must be 'local' or 'cloud'"):
        stations.connection_settings()


def test_cloud_target_uses_the_wallet(monkeypatch):
    for name, value in {
        "ORACLE_TARGET": "cloud",
        "ORACLE_CLOUD_USER": "mobility",
        "ORACLE_CLOUD_PASSWORD": "pw",
        "ORACLE_CLOUD_DSN": "smhub_low",
        "ORACLE_WALLET_DIR": "/wallet",
        "ORACLE_WALLET_PASSWORD": "wpw",
    }.items():
        monkeypatch.setenv(name, value)

    target, kwargs = stations.connection_settings()

    assert target == "cloud"
    assert kwargs["user"] == "mobility"           # never ADMIN
    assert kwargs["wallet_location"] == kwargs["config_dir"] == "/wallet"
