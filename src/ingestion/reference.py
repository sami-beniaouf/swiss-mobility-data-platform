"""Daily export of the Oracle reference tables (stations, cantons) to bronze.

    python -m ingestion.reference

Each run writes a full snapshot of both tables, partitioned by ingestion day, next to the
departures. Fabric reads them through the same shortcut; dbt staging keeps the latest
snapshot (`_batch_id`). The hub stays the single source of truth for reference data.

A table that returns no row is not written: an empty snapshot would become the latest one
and empty the station dimension. The run fails instead, and the previous snapshot stays in use.
"""
import logging
import sys
from datetime import datetime, timezone

import oracledb
import pyarrow as pa

from ingestion.stations import CONNECT_TIMEOUT_S, connection_settings
from ingestion.storage import get_storage, write_batch

log = logging.getLogger("ingestion.reference")

UTC_TS = pa.timestamp("us", tz="UTC")

STATIONS_SCHEMA = pa.schema([
    ("station_id", pa.string()),
    ("station_name", pa.string()),
    ("municipality_bfs_nr", pa.int32()),
    ("canton_code", pa.string()),
    ("lv95_e", pa.float64()),
    ("lv95_n", pa.float64()),
    ("updated_at", UTC_TS),            # last change of the row in the hub
    ("_extracted_at", UTC_TS),
    ("_batch_id", pa.string()),
])

CANTONS_SCHEMA = pa.schema([
    ("canton_code", pa.string()),
    ("canton_name", pa.string()),
    ("language_region", pa.string()),
    ("_extracted_at", UTC_TS),
    ("_batch_id", pa.string()),
])

# bronze dataset -> (query, schema). Columns are selected explicitly: a column added to the
# hub is not exported until it is added here, to the schema contract and to the dbt sources.
REFERENCE_TABLES = {
    "oracle_stations": (
        """SELECT station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n, updated_at
           FROM stations ORDER BY station_id""",
        STATIONS_SCHEMA,
    ),
    "oracle_cantons": (
        """SELECT canton_code, canton_name, language_region
           FROM cantons ORDER BY canton_code""",
        CANTONS_SCHEMA,
    ),
}


def _to_utc(value):
    """Oracle TIMESTAMP columns come back as naive datetimes in the database time zone (UTC)."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _convert(row, schema):
    """Oracle NUMBER(10,2) is returned as Decimal or float; cast to the declared Arrow types."""
    converted = {}
    for field in schema:
        if field.name not in row:
            continue
        value = row[field.name]
        if value is not None:
            if pa.types.is_floating(field.type):
                value = float(value)
            elif pa.types.is_integer(field.type):
                value = int(value)
            elif pa.types.is_timestamp(field.type):
                value = _to_utc(value)
            elif pa.types.is_string(field.type):
                value = str(value)
        converted[field.name] = value
    return converted


def read_table(connection, query, schema):
    """Rows of one query as dicts keyed by the schema's column names (lower case)."""
    with connection.cursor() as cur:
        cur.execute(query)
        columns = [description[0].lower() for description in cur.description]
        return [_convert(dict(zip(columns, values, strict=True)), schema) for values in cur.fetchall()]


def export_reference(storage, connect_kwargs, extracted_at):
    """Read every reference table, then write all snapshots. Returns {dataset: rows written}.

    All tables are read before anything is written, so a failure leaves no partial snapshot.
    """
    batch_id = extracted_at.strftime("%Y%m%dT%H%M%SZ")
    ingestion_date = extracted_at.strftime("%Y-%m-%d")

    snapshots = {}
    with oracledb.connect(**connect_kwargs, tcp_connect_timeout=CONNECT_TIMEOUT_S) as conn:
        for dataset, (query, schema) in REFERENCE_TABLES.items():
            rows = read_table(conn, query, schema)
            if not rows:
                raise ValueError(f"{dataset}: the hub returned 0 rows, snapshot not written")
            for row in rows:
                row["_extracted_at"] = extracted_at
                row["_batch_id"] = batch_id
            snapshots[dataset] = (rows, schema)

    written = {}
    for dataset, (rows, schema) in snapshots.items():
        path = write_batch(storage, rows, schema, dataset, ingestion_date, batch_id)
        log.info("Wrote %d rows to %s", len(rows), path)
        written[dataset] = len(rows)
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)

    extracted_at = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        target, connect_kwargs = connection_settings()
        written = export_reference(get_storage(), connect_kwargs, extracted_at)
    except KeyError as exc:
        log.error("Reference export aborted: missing environment variable %s", exc)
        return 1
    except (oracledb.Error, ValueError) as exc:
        log.error("Reference export failed: %s: %s", type(exc).__name__, str(exc).splitlines()[0])
        return 1
    except Exception:
        log.exception("Reference export failed: could not write to storage")
        return 1

    log.info("Reference export from oracle:%s finished: %s", target, written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
