# Swiss Mobility Data Platform

End-to-end data platform on **Microsoft Fabric** using Swiss public transport open data:
Oracle data hub + REST APIs → Fabric Lakehouse → dbt (Fabric Warehouse) → Power BI,
including a Tableau → Power BI report migration.

> Status: ingestion running in Azure every 15 minutes (Oracle Cloud hub → ADLS bronze) with failure and heartbeat alerts; bronze loaded hourly into a Fabric Lakehouse; silver and gold built by dbt in a Fabric Warehouse (30 tests passing). Power BI report in progress.

## Architecture

```
 Oracle Autonomous DB            transport.opendata.ch (REST)
 stations, cantons                     departures
        │                                  │
        └──────────────┬───────────────────┘
                       │  Azure Function (timer, every 15 min)
                       │  secrets from Key Vault, managed identity
                       ▼
        ADLS Gen2 stswissmobility: bronze (Parquet, partitioned by ingestion day)
                       │  OneLake shortcut
                       ▼
 Fabric Lakehouse ──► dbt-fabric: staging → intermediate → marts (star schema)
                       │
                       ▼
               Power BI (Direct Lake)
```

## Repository layout

| Path | Content |
|---|---|
| `docker-compose.yml` | Local stack: Oracle Free + toolbox |
| `docker/toolbox/` | Dev image: Python 3.13, dbt-fabric, Azure CLI, ODBC Driver 18, sqlcmd, JupyterLab |
| `oracle/sql/` | DDL + reference data for the Oracle hub (26 cantons, 16 stations) |
| `oracle/init/` | Loads `oracle/sql/*.sql` on the first container start |
| `scripts/check_setup.py` | Smoke test of the local stack |
| `src/ingestion/` | Ingestion job: stations from Oracle → stationboard API → bronze Parquet |
| `src/function_app.py`, `src/host.json`, `src/requirements.txt` | Azure Function wrapper (deployment root: `src/`) |
| `notebooks/` | Exploration and design: API structure, retry policy, station loading, polling coverage (01-04), bronze profiling (05), reference data check against swissBOUNDARIES3D (06) |
| `fabric/` | Source of the Fabric notebook that loads bronze into Delta tables |
| `swiss-mobility-dbt/` | dbt project (staging / intermediate / marts + tests) |
| `tests/` | Unit tests of the ingestion (pytest), run in CI |
| `.github/workflows/ci.yml` | CI/CD: lint and tests on every push, deployment to Azure from `main` |

## Local setup (Windows)

**Prerequisites:** Docker Desktop (WSL 2 backend), Git, VS Code.

```powershell
cd C:\Users\soufi\Documents\Portfolio_data\Swiss_Mobility
copy .env.example .env          # then edit the passwords in .env
docker compose up -d --build    # first run: ~5-10 min (image build + Oracle init)
docker compose ps               # sm-oracle must show "healthy"
docker compose exec toolbox python scripts/check_setup.py
```

Expected result: 5 checks `[ OK ]`.

| Service | Address | Credentials |
|---|---|---|
| Oracle (from Windows, e.g. DBeaver / later the Fabric gateway) | `localhost:1521/FREEPDB1` | `ORACLE_APP_USER` / `ORACLE_APP_PASSWORD` from `.env` |
| Oracle (from the toolbox) | `oracle:1521/FREEPDB1` | same |
| JupyterLab | http://localhost:8888 | `JUPYTER_TOKEN` from `.env` |

### Everyday commands

```powershell
docker compose exec toolbox bash        # shell with dbt, az, sqlcmd, python
docker compose logs -f oracle           # watch Oracle start / init scripts
docker compose down                     # stop (data kept)
docker compose down -v                  # stop and wipe Oracle; reference data reloads on next start
```

### Running the ingestion

```powershell
docker compose exec toolbox python -m ingestion.run
```

Each run reads the station list from Oracle (cached in `data/state/` as a fallback), fetches the next departures of every station and appends two Parquet files, partitioned by ingestion day:

```
data/bronze/transport_stationboard/ingestion_date=YYYY-MM-DD/batch_<batch_id>.parquet   one row per departure
data/bronze/_ingestion_log/ingestion_date=YYYY-MM-DD/batch_<batch_id>.parquet           one row per station
```

| Situation | Behaviour |
|---|---|
| Timeout, connection error, HTTP 429/5xx | retried with exponential backoff (2 s, 4 s), max 3 attempts |
| Other HTTP error, departures of another station | station marked as failed, no retry |
| One station fails | other stations continue; failure recorded in the ingestion log |
| More than 50 % of stations fail | logs are written, then the run exits with code 1 |
| Oracle unavailable | cached station list used, warning logged; exit code 1 if no cache exists or it cannot be read |
| Station cache cannot be written | warning logged, departures still fetched |
| Bronze file cannot be written | error logged, exit code 1 |

### Reference data export

```powershell
docker compose exec toolbox python -m ingestion.reference
```

Exports a full snapshot of the hub tables `stations` and `cantons` to bronze, once a day in production:

```
bronze/oracle_stations/ingestion_date=YYYY-MM-DD/batch_<batch_id>.parquet
bronze/oracle_cantons/ingestion_date=YYYY-MM-DD/batch_<batch_id>.parquet
```

Both tables are read before anything is written, and a table with no row fails the run without writing: an empty snapshot would become the latest one and empty the station dimension. dbt staging keeps the latest snapshot (`max(_batch_id)`), so older snapshots remain as history.

### Station hub: local or cloud

The ingestion reads the station list from the Oracle hub selected by `ORACLE_TARGET` in `.env`:

| `ORACLE_TARGET` | Database | Connection |
|---|---|---|
| `local` (default) | Docker container `sm-oracle` | `ORACLE_DSN`, `ORACLE_APP_USER`, `ORACLE_APP_PASSWORD` |
| `cloud` | Oracle Autonomous AI Database (Always Free, eu-zurich-1) | `ORACLE_CLOUD_*` + mTLS wallet in `secrets/oracle_wallet/` (git-ignored) |

The cloud hub is created once with `oracle/cloud/load_hub_as_admin.sql` (run as ADMIN in Database Actions). The `mobility` user needs `CREATE SESSION`, `CREATE TABLE` and a quota on `DATA`.

After changing `.env`, recreate the toolbox so it picks up the new values: `docker compose up -d --force-recreate toolbox`.

### Storage: local or ADLS

`STORAGE_TARGET` in `.env` selects where bronze files and the station cache are written:

| `STORAGE_TARGET` | Location |
|---|---|
| `local` (default) | `data/bronze/…` and `data/state/stations_cache.json` |
| `adls` | storage account `ADLS_ACCOUNT_NAME`, containers `bronze` and `state` |

ADLS authentication uses `DefaultAzureCredential`, so the same code runs everywhere and only the environment selects the identity:

| Environment | Identity |
|---|---|
| Azure Function (production) | system-assigned managed identity, no secret |
| Toolbox (local tests) | service principal `sp-swissmobility-local`: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` in `.env` (secret valid 90 days) |

Each identity has the role **Storage Blob Data Contributor** on the storage account only. The containers `bronze` and `state` must exist; folders inside them are created on write.

Bronze files are append-only: a file is created only if it does not exist yet (condition checked by the service), then its content is appended and committed. If the upload fails, the incomplete file is deleted, so the dataset never contains an empty Parquet file.

Test run against ADLS without changing `.env`:

```powershell
docker compose exec -e STORAGE_TARGET=adls toolbox python -m ingestion.run
```

### Production: Azure Function

The ingestion runs in the Function App `func-swissmobility-sb` (Flex Consumption, Python 3.13, 512 MB), triggered every 15 minutes (`0 */15 * * * *`, UTC). The PC is not involved.

| Resource | Purpose |
|---|---|
| `func-swissmobility-sb` | `ingest_stationboard` runs `ingestion.run.main()` every 15 minutes; `export_reference` runs `ingestion.reference.main()` daily at 04:05 UTC. A non-zero exit code fails the invocation |
| `kv-swissmobility-sb` (Key Vault) | `oracle-cloud-password`, `oracle-wallet-password`, `oracle-wallet-pem-b64` |
| `stswissmobility` (ADLS Gen2) | containers `bronze` and `state` |
| Application Insights | run logs and invocation history |

The Function authenticates with its system-assigned managed identity, which has **Storage Blob Data Contributor** on `stswissmobility` and **Key Vault Secrets User** on the vault. No secret is stored in the app settings:

| App setting | Value |
|---|---|
| `ORACLE_TARGET` / `STORAGE_TARGET` | `cloud` / `adls` |
| `ADLS_ACCOUNT_NAME` | `stswissmobility` |
| `ORACLE_CLOUD_USER` | `mobility` |
| `ORACLE_CLOUD_DSN` | full connect descriptor (no `tnsnames.ora` in the Function) |
| `ORACLE_CLOUD_PASSWORD`, `ORACLE_WALLET_PASSWORD`, `ORACLE_WALLET_PEM_B64` | `@Microsoft.KeyVault(VaultName=kv-swissmobility-sb;SecretName=…)` |

At startup, `function_app.py` decodes the wallet (`ewallet.pem`, base64 in Key Vault) into a temporary folder and sets `ORACLE_WALLET_DIR`. `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` must not be set on the Function, otherwise `DefaultAzureCredential` would use the local service principal instead of the managed identity.

Deployment: automatic from GitHub Actions, see [CI/CD](#cicd).

### Monitoring and alerting

Every invocation is recorded in Application Insights (table `requests`, one row per run). Two log search alert rules query it and notify the action group `ag-swissmobility-oncall` (email):

| Rule | Query | Condition | Detects |
|---|---|---|---|
| `alert-ingestion-run-failed` | `requests` where `name == "ingest_stationboard"` and `success == false` | more than 0 rows in 15 min, evaluated every 15 min | a run ended with exit code 1: more than 50 % of stations failed, storage not writable, or no station list |
| `alert-ingestion-heartbeat` | `requests` where `name == "ingest_stationboard"` and `success == true` | fewer than 1 row in 45 min, evaluated every 15 min | no successful run for three cycles: Function stopped or disabled, code not loading, timer not firing |

Both rules have severity 1 and resolve automatically once a run succeeds. The heartbeat window tolerates two missed runs before alerting, to avoid false alarms on a single late start.

Failures of individual stations do not alert: the run still succeeds and the failure is recorded in the ingestion log (`status = failed`, with the error message), to be reviewed in the data.

Run history over the last hours:

```kusto
requests
| where timestamp > ago(3h)
| where name == "ingest_stationboard"
| project timestamp, success, duration, resultCode
| order by timestamp desc
```

Both rules were tested. A run was failed on purpose with an invalid `ORACLE_TARGET`: `alert-ingestion-run-failed` fired 6 minutes later and resolved after the next successful run. The Function was then disabled to simulate a silent stop: `alert-ingestion-heartbeat` fired and the email was delivered. The email address of an action group must be verified before notifications are delivered.

### CI/CD

`.github/workflows/ci.yml` runs on GitHub Actions:

```
push (any branch) / pull request to main
   └── test:   ruff check src tests  →  pytest (40 tests, no network, no secret)
                  │ green, and push to main only
                  ▼
           deploy: azure/login (OIDC)  →  Azure/functions-action, package src/, remote build
```

| Job | Runs on | Purpose |
|---|---|---|
| `test` | every push and pull request | lint, then the unit tests against the Function's own dependencies (`tests/requirements.txt` includes `src/requirements.txt`) |
| `deploy` | push to `main`, only if `test` passed | replaces the code of `func-swissmobility-sb`; one deployment at a time |

The deploy job authenticates with **workload identity federation**: no secret is stored. The app registration `sp-swissmobility-github` trusts GitHub tokens for `repo:sami-beniaouf/swiss-mobility-data-platform`, branch `main` only, and has the role **Website Contributor** on the Function App only. The repository secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` hold identifiers, not credentials; they are stored as secrets to keep them out of public logs.

A push deploys the code in `src/` (including `host.json` and `requirements.txt`). App settings, Key Vault secrets, role assignments and alert rules are not part of the deployment: a new setting is added to the Function App before the code that uses it is pushed.

Tests locally:

```powershell
docker compose exec toolbox ruff check src tests
docker compose exec toolbox python -m pytest
```

### Fabric: Lakehouse and Warehouse

Workspace `ws-swiss-mobility` (Fabric trial capacity):

| Item | Role |
|---|---|
| `lh_mobility` (Lakehouse) | bronze as Delta tables: `transport_stationboard`, `ingestion_log`, `oracle_stations`, `oracle_cantons` |
| shortcut `Files/bronze` | link to the ADLS container `bronze` (no copy); connection as an organizational account with **Storage Blob Data Reader** on the container only |
| `nb_load_bronze` (notebook, hourly) | reads the Parquet through the shortcut and rewrites the Delta tables (full reload, `mergeSchema` for older files); source in `fabric/nb_load_bronze.py` |
| `wh_mobility` (Warehouse) | silver and gold, built by dbt; reads the Lakehouse tables with cross-database queries (`lh_mobility.dbo.…`) |

Bronze files are plain Parquet, so they are loaded by the notebook rather than exposed directly as tables (a table shortcut requires Delta, and shortcut file transformations were not available in the tenant).

### Transformation with dbt

```
lh_mobility (bronze)            wh_mobility
  transport_stationboard ──►  staging       stg_transport__departures      view
  oracle_stations        ──►                stg_oracle__stations           view
  oracle_cantons         ──►                stg_oracle__cantons            view
                              intermediate  int_departures__enriched       view
                              marts         dim_date, dim_station,         tables
                                            dim_line, fct_departures
                              reference     transport_categories (seed)    table
```

| Layer | Models | Rules |
|---|---|---|
| staging (silver) | one model per source table: types, trimming, deduplication | departures: one row per `station + category + line + scheduled time + destination`, latest poll kept; within a poll, the copy with a known delay wins. Reference tables: latest daily snapshot (`max(_batch_id)`) |
| intermediate (silver) | `int_departures__enriched` | only departures that have taken place (planned time + last known delay before the latest poll); transport mode from the seed; local date and hour; `is_punctual` = delay < `punctuality_threshold_min` (3 min), null when no real-time data |
| marts (gold) | star schema | `fct_departures` (grain: one scheduled departure at one station) with `dim_station` (stations with canton and language region), `dim_line` (category + line + operator), `dim_date` (calendar) |

Punctuality KPI: `SUM(is_punctual) / SUM(has_realtime)`, reported with the real-time coverage (`SUM(has_realtime) / COUNT(*)`).

Tests (`dbt test`, 30): `unique` and `not_null` on every key, `relationships` between facts, dimensions, sources and the seed, `accepted_values` on flags and language regions, and the singular test `assert_delay_within_bounds` (0 to 300 minutes, bounds taken from the profiling).

**Connection.** dbt connects from the toolbox as the service principal `sp-swissmobility-dbt` (Contributor on the workspace; tenant setting "Service principals can use Fabric APIs" enabled). `profiles.yml` (git-ignored, copied from `profiles_example.yml`) uses `authentication: token_credential` with `azure.identity.ClientSecretCredential`: the token is acquired by azure-identity and passed to the driver. `ActiveDirectoryServicePrincipal` is not used because dbt-fabric 1.11 sends an `Authority Id` keyword its driver rejects. Credentials come from `.env` (`AZURE_TENANT_ID`, `DBT_CLIENT_ID`, `DBT_CLIENT_SECRET`).

```powershell
docker compose exec -w /workspace/swiss-mobility-dbt toolbox dbt debug    # configuration and connection
docker compose exec -w /workspace/swiss-mobility-dbt toolbox dbt seed     # transport_categories
docker compose exec -w /workspace/swiss-mobility-dbt toolbox dbt run      # all models, in dependency order
docker compose exec -w /workspace/swiss-mobility-dbt toolbox dbt test     # 30 tests
```

`dbt run --select staging` builds one layer only. The CI parses the project on every push (`dbt parse`, no connection).

## Data sources

- **transport.opendata.ch**: departures (stationboard). Note: in `/v1/locations`, `coordinate.x` is the latitude and `coordinate.y` the longitude.
- **Oracle hub (simulated)**: stations (BPUIC id, BFS municipality number, LV95 coordinates) and cantons (language region).

### Known limitations

Established by profiling the bronze data (`notebooks/05_bronze_profiling.ipynb`):

| Limitation | Effect | Handling |
|---|---|---|
| The stationboard API has no cancellation information | cancelled departures cannot be identified | punctuality covers departures that ran with real-time data |
| Real-time coverage varies by category (S, IR, IC, RE, R: 85-94 %; ICE 45 %; night S-Bahn 32 %) | punctuality of low-coverage categories rests on few departures | reports show the coverage (`has_realtime`) next to the punctuality rate |
| A few cross-border departures have two train numbers (e.g. IR 36 / ICE 109 from Basel, 0.07 % of departures) | counted as two departures | accepted |
| The delay of a departure is the last value seen before it leaves, at most 15 minutes earlier (polling interval) | a delay that grows in the last minutes is not captured | accepted; punctuality is measured on the last known delay |
| The API is unreachable for a few minutes most nights | the stations polled during the outage have no departures in that batch; departures are still captured by the following polls | failed station calls are recorded in the ingestion log; the run fails and alerts above 50 % |
