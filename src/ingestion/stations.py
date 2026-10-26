"""Station list: read from the Oracle data hub, with a local cache as fallback.

Oracle is the single source of truth for the stations (also used by dim_station in dbt).
Every valid list is cached so that the ingestion keeps running when Oracle is unavailable:
the departures API keeps no history, so a missed run is lost permanently.
Only a non-empty list may overwrite the cache.

The target database is selected by environment variables, so the same code runs
locally and in the cloud:

    ORACLE_TARGET=local   Docker Oracle      ORACLE_DSN, ORACLE_APP_USER, ORACLE_APP_PASSWORD
    ORACLE_TARGET=cloud   Autonomous DB      ORACLE_CLOUD_DSN, ORACLE_CLOUD_USER, ORACLE_CLOUD_PASSWORD,
                          (mTLS wallet)      ORACLE_WALLET_DIR, ORACLE_WALLET_PASSWORD

A missing or invalid setting raises immediately: configuration errors must not be
hidden behind the cache fallback.
"""
import json
import logging
import os
from datetime import datetime, timezone

import oracledb

from ingestion.config import STATE_CONTAINER, STATIONS_CACHE_FILE

log = logging.getLogger(__name__)

STATION_QUERY = """
    SELECT station_id, station_name
    FROM stations
    ORDER BY station_id
"""

CONNECT_TIMEOUT_S = 15


def connection_settings():
    """Return (target, connect kwargs) for the database selected by ORACLE_TARGET."""
    target = os.environ.get("ORACLE_TARGET", "local").strip().lower()

    if target == "local":
        return target, {
            "user": os.environ["ORACLE_APP_USER"],
            "password": os.environ["ORACLE_APP_PASSWORD"],
            "dsn": os.environ["ORACLE_DSN"],
        }

    if target == "cloud":
        wallet_dir = os.environ["ORACLE_WALLET_DIR"]
        return target, {
            "user": os.environ["ORACLE_CLOUD_USER"],
            "password": os.environ["ORACLE_CLOUD_PASSWORD"],
            "dsn": os.environ["ORACLE_CLOUD_DSN"],
            "config_dir": wallet_dir,
            "wallet_location": wallet_dir,
            "wallet_password": os.environ["ORACLE_WALLET_PASSWORD"],
        }

    raise ValueError(f"ORACLE_TARGET must be 'local' or 'cloud', got {target!r}")


def _read_oracle(query, connect_kwargs):
    with oracledb.connect(**connect_kwargs, tcp_connect_timeout=CONNECT_TIMEOUT_S) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [{"station_id": str(sid), "station_name": name} for sid, name in cur.fetchall()]


def _write_cache(storage, stations, source, read_at):
    payload = {
        "cached_at": read_at.isoformat(timespec="seconds"),
        "source": source,
        "stations": stations,
    }
    data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    storage.write_bytes(STATE_CONTAINER, STATIONS_CACHE_FILE, data, overwrite=True)


def _read_cache(storage):
    data = storage.read_bytes(STATE_CONTAINER, STATIONS_CACHE_FILE)
    if data is None:
        return None
    payload = json.loads(data.decode("utf-8"))
    if not payload.get("stations"):
        return None
    return payload["stations"], datetime.fromisoformat(payload["cached_at"])


def load_stations(storage, query=STATION_QUERY, settings=None):
    """Return (stations, source, as_of).

    source is "oracle:local", "oracle:cloud" or "cache"; as_of is the UTC time the list was read
    from Oracle (for the cache: the time the cached list was read), so the age of the list used
    by a run is always started_at - as_of.

    The cache lives in the state container of `storage` (local folder or ADLS).
    `settings` overrides the environment, as returned by connection_settings() (used in tests).
    Raises RuntimeError when Oracle fails (or returns no station) and no cache is available.
    """
    target, connect_kwargs = settings or connection_settings()
    source = f"oracle:{target}"

    try:
        stations = _read_oracle(query, connect_kwargs)
        read_at = datetime.now(timezone.utc).replace(microsecond=0)
        if not stations:
            raise ValueError("Oracle returned 0 stations")
    except (oracledb.Error, ValueError) as exc:
        oracle_error = f"{type(exc).__name__}: {exc}".splitlines()[0]
    else:
        # The cache is a fallback only: failing to refresh it must not cost the departures of this run.
        # A storage problem that also affects bronze makes the run fail when the batch is written.
        try:
            _write_cache(storage, stations, source, read_at)
            log.info("Loaded %d stations from %s, cache refreshed", len(stations), source)
        except Exception as exc:
            log.warning("Loaded %d stations from %s, cache NOT refreshed (%s: %s)",
                        len(stations), source, type(exc).__name__, str(exc).splitlines()[0])
        return stations, source, read_at

    try:
        cached = _read_cache(storage)
    except Exception as exc:
        log.error("Station cache unreadable (%s: %s)", type(exc).__name__, str(exc).splitlines()[0])
        cached = None
    if cached is None:
        cache_location = storage.describe(STATE_CONTAINER, STATIONS_CACHE_FILE)
        raise RuntimeError(f"Station list unavailable: {source} failed ({oracle_error}) and no cache at {cache_location}")

    stations, cached_at = cached
    log.warning("%s unavailable (%s). Using %d cached stations from %s",
                source, oracle_error, len(stations), cached_at.isoformat())
    return stations, "cache", cached_at
