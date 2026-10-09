"""SQLite helpers: schema creation and a per-request connection dependency."""

import os
import sqlite3
from collections.abc import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT    NOT NULL,
    sensor      TEXT    NOT NULL,
    value       REAL    NOT NULL,
    unit        TEXT    NOT NULL,
    recorded_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_device_sensor_time
    ON readings (device_id, sensor, recorded_at);
"""


def db_path() -> str:
    """Database file location. Override with the SENSOR_DB_PATH environment variable."""
    return os.environ.get("SENSOR_DB_PATH", "readings.db")


def init_db() -> None:
    conn = sqlite3.connect(db_path())
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one short-lived connection per request."""
    # check_same_thread=False because FastAPI may run a dependency and its
    # endpoint on different worker threads. Each request still gets its own
    # connection, so nothing is shared between requests.
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
