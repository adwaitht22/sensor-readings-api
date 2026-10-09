"""Sensor Readings API: store and query time-stamped readings from devices."""

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .database import get_db, init_db
from .schemas import DeviceStats, Reading, ReadingCreate


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Sensor Readings API",
    description="Ingest and query time-stamped sensor readings (e.g. from ESP32 devices).",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return 422 with a compact error list.

    FastAPI's default handler echoes the rejected input back to the client. For a
    value like NaN that cannot be serialised to JSON, that turned a clean 422 into
    a 500, so the input is left out of the response.
    """
    errors = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


def _to_reading(row: sqlite3.Row) -> Reading:
    return Reading(
        id=row["id"],
        device_id=row["device_id"],
        sensor=row["sensor"],
        value=row["value"],
        unit=row["unit"],
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/readings", response_model=Reading, status_code=201)
def create_reading(payload: ReadingCreate, db: sqlite3.Connection = Depends(get_db)) -> Reading:
    recorded_at = payload.recorded_at or datetime.now(timezone.utc)
    cur = db.execute(
        "INSERT INTO readings (device_id, sensor, value, unit, recorded_at) VALUES (?, ?, ?, ?, ?)",
        (
            payload.device_id,
            payload.sensor,
            payload.value,
            payload.unit,
            recorded_at.isoformat(timespec="microseconds"),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM readings WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _to_reading(row)


@app.get("/readings", response_model=list[Reading])
def list_readings(
    device_id: str | None = None,
    sensor: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
) -> list[Reading]:
    """Newest first. Filter by device and/or sensor; page with limit and offset."""
    clauses, params = [], []
    if device_id is not None:
        clauses.append("device_id = ?")
        params.append(device_id)
    if sensor is not None:
        clauses.append("sensor = ?")
        params.append(sensor)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(
        f"SELECT * FROM readings {where} ORDER BY recorded_at DESC, id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_to_reading(r) for r in rows]


@app.get("/readings/{reading_id}", response_model=Reading)
def get_reading(reading_id: int, db: sqlite3.Connection = Depends(get_db)) -> Reading:
    row = db.execute("SELECT * FROM readings WHERE id = ?", (reading_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return _to_reading(row)


@app.delete("/readings/{reading_id}", status_code=204)
def delete_reading(reading_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    cur = db.execute("DELETE FROM readings WHERE id = ?", (reading_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Reading not found")
    return Response(status_code=204)


@app.get("/devices/{device_id}/stats", response_model=DeviceStats)
def device_stats(
    device_id: str,
    sensor: str | None = None,
    db: sqlite3.Connection = Depends(get_db),
) -> DeviceStats:
    """Count, min, max, average and latest value for a device (optionally one sensor)."""
    where, params = "WHERE device_id = ?", [device_id]
    if sensor is not None:
        where += " AND sensor = ?"
        params.append(sensor)

    agg = db.execute(
        f"SELECT COUNT(*) AS n, MIN(value) AS lo, MAX(value) AS hi, AVG(value) AS mean "
        f"FROM readings {where}",
        params,
    ).fetchone()
    if agg["n"] == 0:
        raise HTTPException(status_code=404, detail="No readings for this device")

    latest = db.execute(
        f"SELECT value, recorded_at FROM readings {where} "
        f"ORDER BY recorded_at DESC, id DESC LIMIT 1",
        params,
    ).fetchone()

    return DeviceStats(
        device_id=device_id,
        sensor=sensor,
        count=agg["n"],
        min=agg["lo"],
        max=agg["hi"],
        avg=round(agg["mean"], 4),
        latest_value=latest["value"],
        latest_recorded_at=datetime.fromisoformat(latest["recorded_at"]),
    )
