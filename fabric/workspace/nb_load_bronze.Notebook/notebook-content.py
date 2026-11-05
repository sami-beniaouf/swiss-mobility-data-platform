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
# Reads the Parquet files written by the ingestion (ADLS, through the `Files/bronze` shortcut) and writes them as Delta tables in `lh_mobility`, where the SQL endpoint and dbt read them. Full reload: each run rewrites the tables from all files.

# CELL ********************

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

for folder, table in DATASETS.items():
    df = (
        spark.read
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

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
