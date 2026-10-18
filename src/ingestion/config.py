"""Ingestion settings. Paths can be overridden with the DATA_ROOT environment variable."""
import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/workspace/data"))

BRONZE_DEPARTURES_DIR = DATA_ROOT / "bronze" / "transport_stationboard"
BRONZE_LOG_DIR = DATA_ROOT / "bronze" / "_ingestion_log"
STATIONS_CACHE_PATH = DATA_ROOT / "state" / "stations_cache.json"

API_URL = "https://transport.opendata.ch/v1/stationboard"
DEPARTURES_PER_STATION = 100
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_S = 15
PAUSE_BETWEEN_STATIONS_S = 0.5      # spread the requests, the API is a free public service

# The run fails (non-zero exit code) when more than this share of stations failed.
# Below it, failures are recorded in the ingestion log and the run succeeds.
MAX_FAILURE_RATIO = 0.5
