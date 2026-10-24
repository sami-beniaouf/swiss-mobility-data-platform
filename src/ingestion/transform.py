"""Flatten stationboard departures into bronze rows, with an explicit Parquet schema.

The schema is the contract with dbt (swiss-mobility-dbt/models/staging/_sources.yml).
"""
from datetime import datetime, timezone

import pyarrow as pa

UTC_TS = pa.timestamp("us", tz="UTC")

DEPARTURES_SCHEMA = pa.schema([
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
])

INGESTION_LOG_SCHEMA = pa.schema([
    ("_batch_id", pa.string()),
    ("station_id", pa.string()),
    ("station_name", pa.string()),
    ("station_source", pa.string()),
    ("station_list_as_of", UTC_TS),     # when the station list was read from Oracle (cache: when it was cached)
    ("status", pa.string()),
    ("rows", pa.int32()),
    ("attempts", pa.int32()),
    ("error", pa.string()),
    ("started_at", UTC_TS),
    ("finished_at", UTC_TS),
])


def to_row(dep, ingested_at, batch_id):
    """One departure -> one bronze row.

    UTC comes from departureTimestamp (Unix epoch, UTC by definition); the original
    local-time string is kept in departure_planned_raw for traceability.
    """
    stop = dep["stop"]
    ts = stop.get("departureTimestamp")
    return {
        "station_id": stop["station"]["id"],
        "category": dep.get("category"),
        "line_number": dep.get("number"),
        "operator": dep.get("operator"),
        "destination": dep.get("to"),
        "departure_planned_utc": datetime.fromtimestamp(ts, tz=timezone.utc) if ts is not None else None,
        "departure_planned_raw": stop.get("departure"),
        "delay_min": stop.get("delay"),
        "platform": stop.get("platform"),
        "_ingested_at": ingested_at,
        "_batch_id": batch_id,
    }
