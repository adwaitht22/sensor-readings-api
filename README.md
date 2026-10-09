# Sensor Readings API

A small REST API for storing and querying time-stamped sensor readings, built with Python, FastAPI and SQLite. It is designed for devices like the ESP32 boards I used in my final-year Visible Light Communication project: a device POSTs a reading, and you can query the history and summary stats.

**Status:** runs locally, 33 automated tests, 100% line coverage (measured with `pytest-cov`). Not deployed yet.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/readings` | Store a reading (validated) |
| `GET` | `/readings` | List readings, newest first. Filters: `device_id`, `sensor`. Paging: `limit` (1-500), `offset` |
| `GET` | `/readings/{id}` | Fetch one reading |
| `DELETE` | `/readings/{id}` | Delete one reading |
| `GET` | `/devices/{device_id}/stats` | Count, min, max, average and latest value (optional `sensor` filter) |

Interactive docs are generated automatically at `/docs` once the server is running.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

The API is now at http://127.0.0.1:8000 (docs at http://127.0.0.1:8000/docs). Data is stored in `readings.db`; set the `SENSOR_DB_PATH` environment variable to use a different file.

## Try it

```bash
curl -X POST http://127.0.0.1:8000/readings \
  -H "Content-Type: application/json" \
  -d '{"device_id": "esp32-01", "sensor": "temperature", "value": 24.5, "unit": "C"}'

curl http://127.0.0.1:8000/devices/esp32-01/stats
```

Example stats response:

```json
{
  "device_id": "esp32-01",
  "sensor": null,
  "count": 2,
  "min": 24.5,
  "max": 26.5,
  "avg": 25.5,
  "latest_value": 26.5,
  "latest_recorded_at": "2026-10-09T08:19:32.189025Z"
}
```

`examples/esp32_post_reading.py` is a MicroPython sketch that posts readings from an ESP32. It has **not been tested on hardware yet**.

## Run the tests

```bash
python -m pytest --cov=app --cov-report=term-missing
```

The suite uses a fresh temporary database for every test and covers validation, filtering, pagination, stats, 404s, and SQL-injection attempts.

## Design notes

- **Validation:** device and sensor names are limited to letters, digits, `_`, `.` and `-`; values must be finite numbers; timestamps are normalised to UTC (a timestamp with no timezone is treated as UTC).
- **SQL safety:** every query uses parameter placeholders. The only SQL assembled from strings is a `WHERE` clause built from fixed column names, never from user input.
- **Index:** `(device_id, sensor, recorded_at)` so the common filtered queries do not scan the whole table.
- **Errors:** invalid input returns 422 with a compact error list. I wrote a custom handler after a test showed that sending `NaN` made FastAPI's default handler return a 500 (it tried to echo the bad value back as JSON).
- **One connection per request**, closed when the request ends.

## Limitations and next steps

- SQLite is fine for one device group or a demo; a busy fleet would need PostgreSQL.
- No authentication yet, so anyone who can reach the server can write to it. API keys per device would be the first thing to add.
- No rate limiting.
- Not deployed. Next step is putting it on AWS EC2 behind a domain.

## How this was built

I built this project with help from Claude (an AI assistant) as a way to put a tested Python backend on my GitHub. Claude wrote the first version of the code and tests from my description. I then read through it, ran it, and now maintain it. The ESP32 integration idea comes from my own VLC project.

*What I learned (in my own words):* <!-- Replace this line after you have read the code and run it yourself. -->
