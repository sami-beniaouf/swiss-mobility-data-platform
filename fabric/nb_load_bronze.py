# Fabric notebook nb_load_bronze (workspace ws-swiss-mobility, default lakehouse lh_mobility).
# Source kept in Git; the notebook in Fabric runs this code on an hourly schedule.
#
# Reads the Parquet files written by the ingestion (ADLS, through the Files/bronze shortcut)
# and writes them as Delta tables in lh_mobility, where the SQL endpoint and dbt read them.
# Full reload: each run rewrites the tables from all files, so a run can be repeated safely.

# Full OneLake paths: independent of the notebook's default lakehouse, so the
# scheduled run behaves exactly like an interactive one.
LAKEHOUSE = "abfss://ws-swiss-mobility@onelake.dfs.fabric.microsoft.com/lh_mobility.Lakehouse"
BRONZE = f"{LAKEHOUSE}/Files/bronze"
TABLES = f"{LAKEHOUSE}/Tables/dbo"

# ADLS folder -> Delta table name
DATASETS = {
    "transport_stationboard": "transport_stationboard",
    "_ingestion_log": "ingestion_log",
    "oracle_stations": "oracle_stations",
    "oracle_cantons": "oracle_cantons",
}

for folder, table in DATASETS.items():
    df = (
        spark.read  # noqa: F821  (spark is provided by the Fabric notebook session)
        .option("mergeSchema", "true")   # older files may lack columns added later
        .parquet(f"{BRONZE}/{folder}")
    )
    (
        df.write
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .format("delta")
        .save(f"{TABLES}/{table}")
    )
    print(f"{table}: {df.count():,} rows, {len(df.columns)} columns")
