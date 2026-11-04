"""Daily export of the Oracle reference tables, with a fake Oracle connection."""
from datetime import datetime, timezone
from decimal import Decimal

import oracledb
import pyarrow.parquet as pq
import pytest

from ingestion import reference
from ingestion.reference import CANTONS_SCHEMA, STATIONS_SCHEMA, export_reference
from ingestion.storage import LocalStorage

EXTRACTED_AT = datetime(2026, 11, 5, 4, 5, tzinfo=timezone.utc)

HUB = {
    "stations": (
        ["STATION_ID", "STATION_NAME", "MUNICIPALITY_BFS_NR", "CANTON_CODE", "LV95_E", "LV95_N", "UPDATED_AT"],
        [
            ("8504300", "Biel/Bienne", 371, "BE", Decimal("2585151.73"), Decimal("1220231.08"),
             datetime(2026, 10, 12, 9, 30)),
            ("8507000", "Bern", 351, "BE", Decimal("2600037.33"), Decimal("1199748.79"),
             datetime(2026, 10, 12, 9, 30)),
        ],
    ),
    "cantons": (
        ["CANTON_CODE", "CANTON_NAME", "LANGUAGE_REGION"],
        [("BE", "Bern", "Bilingual"), ("NE", "Neuchâtel", "French")],
    ),
}


class FakeCursor:
    def __init__(self, hub):
        self.hub, self.description, self.rows = hub, None, []

    def execute(self, query):
        table = "stations" if "FROM stations" in query else "cantons"
        columns, self.rows = self.hub[table]
        self.description = [(name,) for name in columns]

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection(FakeCursor):
    def cursor(self):
        return FakeCursor(self.hub)


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


def use_hub(monkeypatch, hub):
    monkeypatch.setattr(reference.oracledb, "connect", lambda **kwargs: FakeConnection(hub))


def read_snapshot(storage, dataset):
    files = sorted((storage.root / "bronze" / dataset).rglob("*.parquet"))
    assert len(files) == 1
    return files[0], pq.read_table(files[0])


def test_both_tables_are_written_with_their_schema(monkeypatch, storage):
    use_hub(monkeypatch, HUB)

    written = export_reference(storage, {}, EXTRACTED_AT)

    assert written == {"oracle_stations": 2, "oracle_cantons": 2}
    stations_file, stations = read_snapshot(storage, "oracle_stations")
    _, cantons = read_snapshot(storage, "oracle_cantons")
    assert stations_file.parent.name == "ingestion_date=2026-11-05"
    assert stations.schema.equals(STATIONS_SCHEMA)
    assert cantons.schema.equals(CANTONS_SCHEMA)


def test_oracle_types_are_converted(monkeypatch, storage):
    use_hub(monkeypatch, HUB)

    export_reference(storage, {}, EXTRACTED_AT)

    biel = read_snapshot(storage, "oracle_stations")[1].to_pylist()[0]
    assert biel["lv95_e"] == pytest.approx(2585151.73)          # Decimal -> float
    assert biel["updated_at"] == datetime(2026, 10, 12, 9, 30, tzinfo=timezone.utc)   # naive -> UTC


def test_both_snapshots_share_one_batch_id(monkeypatch, storage):
    use_hub(monkeypatch, HUB)

    export_reference(storage, {}, EXTRACTED_AT)

    for dataset in ("oracle_stations", "oracle_cantons"):
        table = read_snapshot(storage, dataset)[1]
        assert set(table.column("_batch_id").to_pylist()) == {"20261105T040500Z"}


def test_empty_table_writes_no_snapshot(monkeypatch, storage):
    empty_cantons = {**HUB, "cantons": (HUB["cantons"][0], [])}
    use_hub(monkeypatch, empty_cantons)

    with pytest.raises(ValueError, match="oracle_cantons: the hub returned 0 rows"):
        export_reference(storage, {}, EXTRACTED_AT)

    # read before write: the stations were valid but nothing was written either
    assert not (storage.root / "bronze").exists()


def test_main_fails_cleanly_when_oracle_is_down(monkeypatch, storage):
    def oracle_down(**kwargs):
        raise oracledb.OperationalError("DPY-6005: cannot connect to database")

    monkeypatch.setattr(reference, "connection_settings", lambda: ("cloud", {}))
    monkeypatch.setattr(reference, "get_storage", lambda: storage)
    monkeypatch.setattr(reference.oracledb, "connect", oracle_down)

    assert reference.main() == 1
