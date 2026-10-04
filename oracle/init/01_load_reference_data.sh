#!/bin/bash
# Runs ONCE, on the first start of the Oracle container (empty data volume).
# Creates the reference tables in the application schema and loads them.
# To rerun: docker compose down -v && docker compose up -d

# UTF-8 client so accents (Neuchâtel, Genève, Zürich) are stored correctly
export NLS_LANG=AMERICAN_AMERICA.AL32UTF8

for script in /opt/mobility-sql/*.sql; do
    echo "[mobility] running ${script}"
    sqlplus -s "${APP_USER}/${APP_USER_PASSWORD}@//localhost:1521/FREEPDB1" @"${script}" \
        || { echo "[mobility] FAILED: ${script}"; exit 1; }
done

echo "[mobility] reference data loaded"
