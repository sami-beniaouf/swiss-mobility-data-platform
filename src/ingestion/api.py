"""Client for the transport.opendata.ch stationboard endpoint.

Transient failures (network errors, HTTP 429/5xx) are retried with exponential backoff.
Permanent failures (other non-200 statuses, departures of another station) fail immediately.
"""
import logging
import time

import requests

from ingestion.config import API_URL, DEPARTURES_PER_STATION, MAX_ATTEMPTS, REQUEST_TIMEOUT_S

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """Final failure for one station. Carries the number of attempts for the ingestion log."""

    def __init__(self, message, attempts):
        super().__init__(message)
        self.attempts = attempts


def fetch_stationboard(
    station_id,
    session=None,
    limit=DEPARTURES_PER_STATION,
    max_attempts=MAX_ATTEMPTS,
    timeout_s=REQUEST_TIMEOUT_S,
    api_url=API_URL,
):
    """Return (departures, attempts_used) for one station. Raises FetchError on final failure."""
    http = session or requests

    for attempt in range(1, max_attempts + 1):
        is_last = attempt == max_attempts
        wait_s = 2 ** attempt                      # backoff: 2 s, then 4 s

        try:
            response = http.get(api_url, params={"id": station_id, "limit": limit}, timeout=timeout_s)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if is_last:
                raise FetchError(f"{type(exc).__name__} after {attempt} attempts", attempt) from exc
            log.warning("[%s] attempt %d failed (%s), retrying in %ds", station_id, attempt, type(exc).__name__, wait_s)
            time.sleep(wait_s)
            continue

        if response.status_code in RETRYABLE_STATUS:
            if is_last:
                raise FetchError(f"HTTP {response.status_code} after {attempt} attempts", attempt)
            log.warning("[%s] attempt %d failed (HTTP %d), retrying in %ds", station_id, attempt, response.status_code, wait_s)
            time.sleep(wait_s)
            continue

        if response.status_code != 200:
            raise FetchError(f"HTTP {response.status_code} (permanent)", attempt)

        try:
            departures = response.json()["stationboard"]
        except (ValueError, KeyError) as exc:
            raise FetchError(f"Unexpected response body ({type(exc).__name__})", attempt) from exc

        # Unknown ids are not rejected by the API: it falls back to a name search and returns
        # HTTP 200 with another station's departures. Every departure is validated.
        for dep in departures:
            returned_id = dep["stop"]["station"]["id"]
            if returned_id != station_id:
                raise FetchError(f"Station mismatch: asked for {station_id}, got {returned_id}", attempt)

        return departures, attempt
