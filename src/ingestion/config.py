"""Ingestion settings.

Storage is selected with STORAGE_TARGET:
    local (default)  files under DATA_ROOT/<container>/...  (DATA_ROOT defaults to /workspace/data)
    adls             Azure Data Lake Storage Gen2 account ADLS_ACCOUNT_NAME, authenticated with
                     DefaultAzureCredential (managed identity in Azure, `az login` locally)
"""
import os
from pathlib import Path

STORAGE_TARGET = os.environ.get("STORAGE_TARGET", "local").strip().lower()
DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/workspace/data"))
ADLS_ACCOUNT_NAME = os.environ.get("ADLS_ACCOUNT_NAME")

# Containers (local: sub-folders of DATA_ROOT) and paths inside them
BRONZE_CONTAINER = "bronze"
STATE_CONTAINER = "state"
DEPARTURES_DATASET = "transport_stationboard"
INGESTION_LOG_DATASET = "_ingestion_log"
STATIONS_CACHE_FILE = "stations_cache.json"

API_URL = "https://transport.opendata.ch/v1/stationboard"
DEPARTURES_PER_STATION = 100        # sized for a 15-minute schedule (see notebooks/04_poll_coverage.ipynb)
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_S = 15
PAUSE_BETWEEN_STATIONS_S = 0.5      # spread the requests, the API is a free public service

# The run fails (non-zero exit code) when more than this share of stations failed.
# Below it, failures are recorded in the ingestion log and the run succeeds.
MAX_FAILURE_RATIO = 0.5
