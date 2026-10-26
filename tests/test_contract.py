"""Bronze schema contract.

The Parquet files are read by dbt (models/staging/_sources.yml) and accumulate over time.
Renaming a column or changing a type does not fail the ingestion: it silently produces
NULLs downstream. These tests make such a change fail before deployment, so that it is
made deliberately, together with the dbt sources.
"""
import pyarrow as pa
import yaml

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


def _as_list(schema):
    return [(field.name, field.type) for field in schema]


def test_departures_schema_is_unchanged():
    assert _as_list(DEPARTURES_SCHEMA) == EXPECTED_DEPARTURES


def test_ingestion_log_schema_is_unchanged():
    assert _as_list(INGESTION_LOG_SCHEMA) == EXPECTED_INGESTION_LOG


def test_dbt_source_declares_the_same_columns(repo_root):
    sources_file = repo_root / "swiss-mobility-dbt" / "models" / "staging" / "_sources.yml"
    sources = yaml.safe_load(sources_file.read_text(encoding="utf-8"))["sources"]
    transport = next(s for s in sources if s["name"] == "bronze_transport")
    table = next(t for t in transport["tables"] if t["name"] == "transport_stationboard")

    declared = [column["name"] for column in table["columns"]]
    written = [field.name for field in DEPARTURES_SCHEMA]
    assert declared == written
