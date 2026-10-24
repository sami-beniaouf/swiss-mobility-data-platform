# Swiss Mobility Data Platform

End-to-end data platform on **Microsoft Fabric** using Swiss public transport open data:
Oracle data hub + REST APIs → Fabric Lakehouse → dbt (Fabric Warehouse) → Power BI,
including a Tableau → Power BI report migration.

> Status: ingestion running in Azure every 15 minutes (Oracle Cloud hub → ADLS bronze). Fabric layer in progress.

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
| `notebooks/` | Exploration and design of the ingestion (API structure, retry policy, station loading) |
| `swiss-mobility-dbt/` | dbt project (staging / intermediate / marts + tests) |

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
| `func-swissmobility-sb` | runs `ingestion.run.main()`; a non-zero exit code fails the invocation |
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

Deployment: VS Code, Azure Functions extension, **Deploy to Function App** (`.vscode/settings.json` sets `src` as deployment folder, with remote build).

### Connecting dbt to Fabric (once the Fabric workspace exists)

```bash
# inside the toolbox
az login --use-device-code
cp swiss-mobility-dbt/profiles_example.yml swiss-mobility-dbt/profiles.yml   # fill in the SQL endpoint
cd swiss-mobility-dbt && dbt debug
```

## Data sources

- **transport.opendata.ch**: departures (stationboard). Note: in `/v1/locations`, `coordinate.x` is the latitude and `coordinate.y` the longitude.
- **Oracle hub (simulated)**: stations (BPUIC id, BFS municipality number, LV95 coordinates) and cantons (language region).
