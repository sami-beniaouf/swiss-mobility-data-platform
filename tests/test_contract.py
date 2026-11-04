"""Bronze schema contract.

The Parquet files are read by dbt (models/staging/_sources.yml) and accumulate over time.
Renaming a column or changing a type does not fail the ingestion: it silently produces
NULLs downstream. These tests make such a change fail before deployment, so that it is
made deliberately, together with the dbt sources.
"""
import pyarrow as pa
import pytest
import yaml

from ingestion.reference import CANTONS_SCHEMA, STATIONS_SCHEMA
from ingestion.transform import DEPARTURES_SCHEMA, INGESTION_LOG_SCHEMA

UTC_TS = pa.timestamp("us", tz="UTC")

EXPECTED_DEPARTURES = [
    ("station_id", pa.string()),
    ("category", pa.string()),
    ("line_number", pa.string()),
    ("operator", pa.string()),
    ("destination", pa.string()),
    ("departure_planned_utc", UTC_TS),
    ("departure_planned_raw", pa.string()),
    ("delay_min", pa.int32()),
    ("platform", pa.string()),
    ("_ingested_at", UTC_TS),
    ("_batch_id", pa.string()),
]

EXPECTED_INGESTION_LOG = [
    ("_batch_id", pa.string()),
    ("station_id", pa.string()),
    ("station_name", pa.string()),
    ("station_source", pa.string()),
    ("station_list_as_of", UTC_TS),
    ("status", pa.string()),
    ("rows", pa.int32()),
    ("attempts", pa.int32()),
    ("error", pa.string()),
    ("started_at", UTC_TS),
    ("finished_at", UTC_TS),
]


EXPECTED_STATIONS = [
    ("station_id", pa.string()),
    ("station_name", pa.string()),
    ("municipality_bfs_nr", pa.int32()),
    ("canton_code", pa.string()),
    ("lv95_e", pa.float64()),
    ("lv95_n", pa.float64()),
    ("updated_at", UTC_TS),
    ("_extracted_at", UTC_TS),
    ("_batch_id", pa.string()),
]

EXPECTED_CANTONS = [
    ("canton_code", pa.string()),
    ("canton_name", pa.string()),
    ("language_region", pa.string()),
    ("_extracted_at", UTC_TS),
    ("_batch_id", pa.string()),
]


def _as_list(schema):
    return [(field.name, field.type) for field in schema]


def test_departures_schema_is_unchanged():
    assert _as_list(DEPARTURES_SCHEMA) == EXPECTED_DEPARTURES


def test_ingestion_log_schema_is_unchanged():
    assert _as_list(INGESTION_LOG_SCHEMA) == EXPECTED_INGESTION_LOG


def test_reference_schemas_are_unchanged():
    assert _as_list(STATIONS_SCHEMA) == EXPECTED_STATIONS
    assert _as_list(CANTONS_SCHEMA) == EXPECTED_CANTONS


def _declared_columns(repo_root, source_name, table_name):
    sources_file = repo_root / "swiss-mobility-dbt" / "models" / "staging" / "_sources.yml"
    sources = yaml.safe_load(sources_file.read_text(encoding="utf-8"))["sources"]
    source = next(s for s in sources if s["name"] == source_name)
    table = next(t for t in source["tables"] if t["name"] == table_name)
    return [column["name"] for column in table["columns"]]


@pytest.mark.parametrize(
    ("source_name", "table_name", "schema"),
    [
        ("bronze_transport", "transport_stationboard", DEPARTURES_SCHEMA),
        ("bronze_oracle", "oracle_stations", STATIONS_SCHEMA),
        ("bronze_oracle", "oracle_cantons", CANTONS_SCHEMA),
    ],
)
def test_dbt_source_declares_the_same_columns(repo_root, source_name, table_name, schema):
    assert _declared_columns(repo_root, source_name, table_name) == [field.name for field in schema]
