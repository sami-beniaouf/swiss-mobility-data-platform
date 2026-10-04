"""Smoke test for the local stack. Run inside the toolbox:

    docker compose exec toolbox python scripts/check_setup.py

Checks: Oracle reachable + reference data loaded, transport API reachable,
dbt / Azure CLI / sqlcmd installed.
"""
import os
import shutil
import subprocess

import oracledb
import requests

OK, FAIL = "[ OK ]", "[FAIL]"
failures = 0


def check(label, fn):
    global failures
    try:
        detail = fn()
        print(f"{OK} {label}: {detail}")
    except Exception as exc:  # noqa: BLE001 - smoke test, show any error
        failures += 1
        print(f"{FAIL} {label}: {exc}")


def oracle_counts():
    with oracledb.connect(
        user=os.environ["ORACLE_APP_USER"],
        password=os.environ["ORACLE_APP_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
    ) as conn, conn.cursor() as cur:
        counts = {}
        for table in ("cantons", "stations"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
        cur.execute("SELECT station_name FROM stations WHERE station_id = '8504221'")
        accent_check = cur.fetchone()[0]
    if counts != {"cantons": 26, "stations": 16}:
        raise ValueError(f"unexpected row counts {counts}")
    if accent_check != "Neuchâtel":
        raise ValueError(f"encoding problem, got {accent_check!r}")
    return f"{counts}, accents OK"


def transport_api():
    r = requests.get(
        "https://transport.opendata.ch/v1/stationboard",
        params={"id": "8504300", "limit": 3},
        timeout=15,
    )
    r.raise_for_status()
    board = r.json()["stationboard"]
    return " | ".join(f"{d['category']}{d['number']} -> {d['to']}" for d in board)


def command(cmd):
    def run():
        if shutil.which(cmd[0]) is None:
            raise FileNotFoundError(f"{cmd[0]} not on PATH")
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        return out.strip().splitlines()[0]
    return run


def odbc_driver():
    with open("/etc/odbcinst.ini", encoding="utf-8") as f:
        if "ODBC Driver 18 for SQL Server" not in f.read():
            raise ValueError("ODBC Driver 18 not registered")
    if shutil.which("sqlcmd") is None:
        raise FileNotFoundError("sqlcmd not on PATH")
    return "ODBC Driver 18 + sqlcmd available"


check("Oracle reference data", oracle_counts)
check("transport.opendata.ch (Biel/Bienne)", transport_api)
check("dbt", command(["dbt", "--version"]))
check("Azure CLI", command(["az", "version", "--query", '"azure-cli"', "-o", "tsv"]))
check("SQL Server tools", odbc_driver)

print()
print("All checks passed." if failures == 0 else f"{failures} check(s) failed.")
raise SystemExit(1 if failures else 0)
