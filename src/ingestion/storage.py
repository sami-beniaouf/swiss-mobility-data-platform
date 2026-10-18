"""Append-only Parquet storage, partitioned by ingestion day (Hive style).

    <root>/ingestion_date=YYYY-MM-DD/batch_<batch_id>.parquet

Parquet files cannot be appended to, so every run writes its own file and never
modifies existing ones.
"""
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def write_batch(rows, schema: pa.Schema, root: Path, ingestion_date: str, batch_id: str) -> Path:
    """Write rows as one Parquet file. The write is atomic (temporary file, then rename)."""
    partition_dir = root / f"ingestion_date={ingestion_date}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    target = partition_dir / f"batch_{batch_id}.parquet"
    tmp = target.with_suffix(".parquet.tmp")

    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, tmp)
    os.replace(tmp, target)
    return target
