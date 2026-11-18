# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Load bronze into Delta tables
# 
# Incremental load: only bronze files not yet in a table are read and appended. Each row keeps its source file in _source_file. Set FULL_REFRESH = True to rebuild every table from all files.

# CELL ********************

from delta.tables import DeltaTable
from pyspark.sql import functions as F

# Full OneLake paths: independent of the notebook's default lakehouse, so the
# scheduled run behaves exactly like an interactive one.
LAKEHOUSE = "abfss://ws-swiss-mobility@onelake.dfs.fabric.microsoft.com/lh_mobility.Lakehouse"
BRONZE = f"{LAKEHOUSE}/Files/bronze"
TABLES = f"{LAKEHOUSE}/Tables/dbo"          # without schemas: f"{LAKEHOUSE}/Tables"

# ADLS folder -> Delta table name
DATASETS = {
    "transport_stationboard": "transport_stationboard",
    "_ingestion_log": "ingestion_log",
    "oracle_stations": "oracle_stations",
    "oracle_cantons": "oracle_cantons",
}

# True rebuilds every table from all files (after a schema change or to repair a table).
FULL_REFRESH = False

# Bronze files are immutable: one new file per ingestion run, never rewritten.
# A file is identified by its path relative to the dataset folder.
FILE_KEY = r"(ingestion_date=[^/]+/[^/]+\.parquet)$"


def list_files(folder):
    """Relative paths 'ingestion_date=.../batch_....parquet' of every file of a dataset."""
    files = []
    for day in notebookutils.fs.ls(f"{BRONZE}/{folder}"):
        name = day.name.rstrip("/")
        if day.isDir and name.startswith("ingestion_date="):
            files += [f"{name}/{f.name}" for f in notebookutils.fs.ls(day.path) if f.name.endswith(".parquet")]
    return files


def loaded_files(table_path):
    """Files already loaded into the Delta table, or None if the table must be rebuilt."""
    if not DeltaTable.isDeltaTable(spark, table_path):
        return None
    table = spark.read.format("delta").load(table_path)
    if "_source_file" not in table.columns:
        return None
    return {row[0] for row in table.select("_source_file").distinct().collect()}


def read_files(folder, files=None):
    """Read all files of a dataset, or only the given ones, and tag each row with its file."""
    base = f"{BRONZE}/{folder}"
    reader = spark.read.option("mergeSchema", "true").option("basePath", base)  # keeps ingestion_date
    df = reader.parquet(base) if files is None else reader.parquet(*[f"{base}/{f}" for f in files])
    df = df.withColumn("_source_file", F.regexp_extract(F.col("_metadata.file_path"), FILE_KEY, 1))
    # An empty key would make the next run load the file again: stop instead.
    if df.filter(F.col("_source_file") == "").limit(1).count():
        raise ValueError(f"{folder}: unexpected file path, cannot identify the source file")
    return df


for folder, table in DATASETS.items():
    path = f"{TABLES}/{table}"
    all_files = list_files(folder)
    done = None if FULL_REFRESH else loaded_files(path)

    if done is None:
        df = read_files(folder)
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)
        print(f"{table}: full load, {len(all_files)} files, {df.count():,} rows")
        continue

    new_files = sorted(set(all_files) - done)
    if not new_files:
        print(f"{table}: up to date, {len(all_files)} files already loaded")
        continue

    df = read_files(folder, new_files)
    df.write.format("delta").mode("append").option("mergeSchema", "true").save(path)
    print(f"{table}: appended {len(new_files)} new files, {df.count():,} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
