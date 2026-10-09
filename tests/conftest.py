import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client backed by a fresh temporary database for every test."""
    monkeypatch.setenv("SENSOR_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:  # entering the context runs the startup (init_db)
        yield c


def make_reading(**overrides):
    body = {
        "device_id": "esp32-01",
        "sensor": "temperature",
        "value": 24.5,
        "unit": "C",
    }
    body.update(overrides)
    return body
