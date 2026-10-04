# swiss_mobility — dbt project

Transformation layer of the Swiss Mobility Data Platform: Fabric Lakehouse (bronze) → Fabric Warehouse (staging → intermediate → marts) → Power BI.

## Lineage

```
lh_mobility (Lakehouse, bronze)              wh_mobility (Warehouse)
──────────────────────────────               ─────────────────────────────────────────────────────────
transport_stationboard ──▶ stg_transport__departures ──▶ int_departures__enriched ──┬─▶ fct_departures
                                                          ▲                         └─▶ dim_line
seed: transport_categories ───────────────────────────────┘
oracle_stations ─────────▶ stg_oracle__stations ──┬─────────────────────────────────▶ dim_station
oracle_cantons ──────────▶ stg_oracle__cantons ───┘
(generated)                                                                          dim_date
```

Full interactive lineage: `dbt docs generate && dbt docs serve`.

## Layers

| Layer | Schema | Materialization | Rule |
|---|---|---|---|
| staging | `staging` | view | 1:1 with a source. Rename, cast, dedupe. No joins. |
| intermediate | `intermediate` | view | Joins and business logic (punctuality rule). |
| marts | `marts` | table | Star schema consumed by Power BI. |
| seeds | `reference` | table | Small static mappings (transport categories). |

## Star schema

- **fct_departures**: grain = one scheduled departure at one station
- **dim_station**: Oracle hub stations + canton, LV95 coordinates
- **dim_line**: category / line number / operator / mode
- **dim_date**: calendar, Monday = 1

Punctuality KPI (Power BI measure): `DIVIDE(SUM(fct_departures[is_punctual]), SUM(fct_departures[has_realtime]))`.
A departure is punctual when delay < 3 min (`var('punctuality_threshold_min')`).

## Data quality

- Generic tests: unique / not_null on every key, relationships between facts and dimensions, accepted values
- Singular test: `tests/assert_delay_within_bounds.sql`
- Source freshness on bronze transport data: warn after 6 h, error after 24 h (`dbt source freshness`)
- Relationship tests from API data to the Oracle hub are `severity: warn`: the API can return stations the hub doesn't know yet, and that should be visible but not block the pipeline.

## Setup

```bash
pip install dbt-fabric          # needs Microsoft ODBC Driver 18 for SQL Server
az login                        # dev auth = Azure CLI
cp profiles_example.yml ~/.dbt/profiles.yml   # then fill in the Warehouse SQL endpoint
dbt debug
dbt seed
dbt build                       # run models + tests in DAG order
```

## Assumptions to verify on first run

- The Warehouse reads Lakehouse tables cross-database (`lh_mobility.dbo.<table>`); both items must be in the same workspace.
- `stg_transport__departures` uses `AT TIME ZONE` for UTC → Swiss local time. If the Warehouse rejects it, convert in the ingestion notebook instead.
- Bronze column names match `models/staging/_sources.yml` (written by `nb_ingest_transport`).

## Next steps

- `fct_departures` as incremental model once volume grows
- Add ASTRA traffic counts as a second API source
- GitHub Actions: `dbt build` against the dev Warehouse on every PR
