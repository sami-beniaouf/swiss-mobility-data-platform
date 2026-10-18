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
from pathlib import Path

import oracledb

from ingestion.config import STATIONS_CACHE_PATH

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


def _write_cache(stations, source, cache_path: Path):
    """Atomic write: a crash during the write never leaves a half-written cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "stations": stations,
    }
    tmp_path = cache_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, cache_path)


def _read_cache(cache_path: Path):
    if not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not payload.get("stations"):
        return None
    return payload["stations"], payload["cached_at"]


def load_stations(cache_path=STATIONS_CACHE_PATH, query=STATION_QUERY, settings=None):
    """Return (stations, source), source being "oracle:local", "oracle:cloud" or "cache".

    `settings` overrides the environment, as returned by connection_settings() (used in tests).
    Raises RuntimeError when Oracle fails (or returns no station) and no cache is available.
    """
    target, connect_kwargs = settings or connection_settings()
    source = f"oracle:{target}"

    try:
        stations = _read_oracle(query, connect_kwargs)
        if not stations:
            raise ValueError("Oracle returned 0 stations")
        _write_cache(stations, source, cache_path)
        log.info("Loaded %d stations from %s, cache refreshed", len(stations), source)
        return stations, source
    except (oracledb.Error, ValueError) as exc:
        oracle_error = f"{type(exc).__name__}: {exc}".splitlines()[0]

    cached = _read_cache(cache_path)
    if cached is None:
        raise RuntimeError(f"Station list unavailable: {source} failed ({oracle_error}) and no cache at {cache_path}")

    stations, cached_at = cached
    log.warning("%s unavailable (%s). Using %d cached stations from %s",
                source, oracle_error, len(stations), cached_at)
    return stations, "cache"
