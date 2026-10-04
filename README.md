# Swiss Mobility Data Platform

End-to-end data platform on **Microsoft Fabric** using Swiss public transport open data:
Oracle data hub + REST APIs → Fabric Lakehouse → dbt (Fabric Warehouse) → Power BI,
including a Tableau → Power BI report migration.

> Status: local development stack ready (Oracle hub + toolbox). Fabric layer in progress.

## Architecture

```
 Oracle Free (Docker)            transport.opendata.ch (REST)
 stations, cantons                     departures
        │  on-prem data gateway            │  PySpark notebook
        ▼                                  ▼
 ┌──────────────────── Fabric Lakehouse (bronze) ────────────────────┐
 └────────────────────────────────┬──────────────────────────────────┘
                                  │  dbt-fabric
                                  ▼
            Fabric Warehouse: staging → intermediate → marts (star schema)
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
