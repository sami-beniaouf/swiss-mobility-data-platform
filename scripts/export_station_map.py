"""Export the stations with their punctuality to a GeoPackage for QGIS.

    docker compose exec toolbox python scripts/export_station_map.py [--days 14]

Reads the gold layer of the Fabric Warehouse (dim_station, fct_departures) as the service
principal used by dbt, and writes one point per station in Swiss LV95 (EPSG:2056):

    data/gis/station_punctuality.gpkg   layer "station_punctuality"

The rates follow the semantic model: punctuality is measured at departure, on departures
with real-time data, with the 3-minute threshold. The output is a generated file
(data/ is git-ignored); the QGIS project in gis/ references it by relative path.
"""
import argparse
import os
import struct
from itertools import chain, repeat
from pathlib import Path

import geopandas as gpd
import mssql_python
import pandas as pd
from azure.identity import ClientSecretCredential

OUTPUT = Path("/workspace/data/gis/station_punctuality.gpkg")
LAYER = "station_punctuality"
SQL_COPT_SS_ACCESS_TOKEN = 1256
SQL_SCOPE = "https://database.windows.net/.default"

QUERY = """
    select
        s.station_id,
        s.station_name,
        s.canton_code,
        s.canton_name,
        s.language_region,
        s.municipality_bfs_nr,
        s.lv95_e,
        s.lv95_n,
        count(*)                                  as departures,
        sum(f.has_realtime)                       as departures_realtime,
        sum(f.has_realtime) - sum(f.is_punctual)  as late_departures,
        avg(cast(f.delay_min as float))           as avg_delay_min,
        min(d.calendar_date)                      as period_start,
        max(d.calendar_date)                      as period_end
    from marts.fct_departures f
    join marts.dim_station s on s.station_id = f.station_id
    join marts.dim_date d on d.date_key = f.date_key
    where d.calendar_date > dateadd(day, -1 * ?, cast(getdate() as date))   -- last N days, today included
    group by s.station_id, s.station_name, s.canton_code, s.canton_name, s.language_region,
             s.municipality_bfs_nr, s.lv95_e, s.lv95_n
"""


def _token_attrs():
    """Access token for the Warehouse, packed the way the SQL driver expects it."""
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["DBT_CLIENT_ID"],
        client_secret=os.environ["DBT_CLIENT_SECRET"],
    )
    token = credential.get_token(SQL_SCOPE).token.encode("utf-8")
    encoded = bytes(chain.from_iterable(zip(token, repeat(0))))      # UTF-16-LE
    return {SQL_COPT_SS_ACCESS_TOKEN: struct.pack("<i", len(encoded)) + encoded}


def read_stations(days):
    connection_string = (
        f"Server={os.environ['FABRIC_SQL_SERVER']},1433;Database=wh_mobility;"
        "Encrypt=yes;TrustServerCertificate=no"
    )
    with mssql_python.connect(connection_string, attrs_before=_token_attrs()) as conn:
        cursor = conn.cursor()
        cursor.execute(QUERY, (days,))
        columns = [c[0] for c in cursor.description]
        return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)


def to_layer(df):
    """Add the rates and the LV95 point geometry."""
    df = df.copy()
    for column in ("lv95_e", "lv95_n", "avg_delay_min"):
        df[column] = df[column].astype(float)
    realtime = df["departures_realtime"].astype(float)
    df["late_rate"] = (df["late_departures"] / realtime.where(realtime > 0)).round(4)
    df["departure_punctuality"] = (1 - df["late_rate"]).round(4)
    df["realtime_coverage"] = (realtime / df["departures"]).round(4)
    df["avg_delay_min"] = df["avg_delay_min"].round(2)
    df["period_start"] = df["period_start"].astype(str)
    df["period_end"] = df["period_end"].astype(str)
    geometry = gpd.points_from_xy(df["lv95_e"], df["lv95_n"], crs="EPSG:2056")
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:2056")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=14, help="period in days, ending today (default 14)")
    args = parser.parse_args()

    layer = to_layer(read_stations(args.days))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    layer.to_file(OUTPUT, layer=LAYER, driver="GPKG")

    print(f"{len(layer)} stations, {layer['period_start'].min()} to {layer['period_end'].max()} -> {OUTPUT}")
    print(layer[["station_name", "departures", "late_rate", "realtime_coverage"]]
          .sort_values("late_rate", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
