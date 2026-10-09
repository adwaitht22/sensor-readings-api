import pytest

from .conftest import make_reading


# ---------- health ----------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------- creating readings ----------

def test_create_reading_returns_201_and_the_stored_row(client):
    r = client.post("/readings", json=make_reading())
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["device_id"] == "esp32-01"
    assert body["sensor"] == "temperature"
    assert body["value"] == 24.5
    assert body["unit"] == "C"


def test_recorded_at_defaults_to_now_in_utc(client):
    body = client.post("/readings", json=make_reading()).json()
    assert body["recorded_at"].endswith("Z") or body["recorded_at"].endswith("+00:00")


def test_explicit_null_timestamp_also_defaults_to_now(client):
    r = client.post("/readings", json=make_reading(recorded_at=None))
    assert r.status_code == 201
    assert r.json()["recorded_at"] is not None


def test_timestamp_without_timezone_is_treated_as_utc(client):
    body = client.post(
        "/readings", json=make_reading(recorded_at="2026-01-01T10:00:00")
    ).json()
    assert body["recorded_at"].startswith("2026-01-01T10:00:00")


def test_timestamp_with_offset_is_converted_to_utc(client):
    body = client.post(
        "/readings", json=make_reading(recorded_at="2026-01-01T10:00:00+05:30")
    ).json()
    assert body["recorded_at"].startswith("2026-01-01T04:30:00")


@pytest.mark.parametrize(
    "bad",
    [
        {"device_id": ""},
        {"device_id": "has space"},
        {"device_id": "x" * 65},
        {"device_id": "'; DROP TABLE readings;--"},
        {"sensor": ""},
        {"sensor": "bad/sensor"},
        {"unit": ""},
        {"unit": "u" * 17},
        {"value": "not a number"},
    ],
)
def test_invalid_payloads_are_rejected(client, bad):
    r = client.post("/readings", json=make_reading(**bad))
    assert r.status_code == 422


def test_missing_field_is_rejected(client):
    body = make_reading()
    del body["value"]
    assert client.post("/readings", json=body).status_code == 422


def test_nan_value_is_rejected(client):
    raw = '{"device_id": "d1", "sensor": "s", "value": NaN, "unit": "C"}'
    r = client.post("/readings", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


# ---------- reading back ----------

def test_get_reading_by_id(client):
    created = client.post("/readings", json=make_reading(value=1.5)).json()
    r = client.get(f"/readings/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


def test_get_unknown_reading_returns_404(client):
    assert client.get("/readings/999").status_code == 404


def test_list_is_newest_first(client):
    client.post("/readings", json=make_reading(value=1, recorded_at="2026-01-01T00:00:00Z"))
    client.post("/readings", json=make_reading(value=3, recorded_at="2026-01-03T00:00:00Z"))
    client.post("/readings", json=make_reading(value=2, recorded_at="2026-01-02T00:00:00Z"))
    values = [r["value"] for r in client.get("/readings").json()]
    assert values == [3, 2, 1]


def test_list_filters_by_device_and_sensor(client):
    client.post("/readings", json=make_reading(device_id="a", sensor="temperature"))
    client.post("/readings", json=make_reading(device_id="a", sensor="humidity", unit="%"))
    client.post("/readings", json=make_reading(device_id="b", sensor="temperature"))

    assert len(client.get("/readings", params={"device_id": "a"}).json()) == 2
    assert len(client.get("/readings", params={"sensor": "temperature"}).json()) == 2
    both = client.get("/readings", params={"device_id": "a", "sensor": "humidity"}).json()
    assert len(both) == 1 and both[0]["unit"] == "%"


def test_list_pagination(client):
    for i in range(5):
        client.post("/readings", json=make_reading(value=i, recorded_at=f"2026-01-0{i + 1}T00:00:00Z"))
    page1 = client.get("/readings", params={"limit": 2}).json()
    page2 = client.get("/readings", params={"limit": 2, "offset": 2}).json()
    assert [r["value"] for r in page1] == [4, 3]
    assert [r["value"] for r in page2] == [2, 1]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}])
def test_list_rejects_out_of_range_paging(client, params):
    assert client.get("/readings", params=params).status_code == 422


def test_query_params_are_not_vulnerable_to_sql_injection(client):
    client.post("/readings", json=make_reading())
    r = client.get("/readings", params={"device_id": "x' OR '1'='1"})
    assert r.status_code == 200
    assert r.json() == []  # injected text matched nothing
    assert len(client.get("/readings").json()) == 1  # table still intact


# ---------- deleting ----------

def test_delete_reading(client):
    created = client.post("/readings", json=make_reading()).json()
    assert client.delete(f"/readings/{created['id']}").status_code == 204
    assert client.get(f"/readings/{created['id']}").status_code == 404


def test_delete_unknown_reading_returns_404(client):
    assert client.delete("/readings/999").status_code == 404


# ---------- stats ----------

def test_device_stats(client):
    for v, ts in [(10, "2026-01-01T00:00:00Z"), (20, "2026-01-02T00:00:00Z"), (30, "2026-01-03T00:00:00Z")]:
        client.post("/readings", json=make_reading(value=v, recorded_at=ts))

    r = client.get("/devices/esp32-01/stats")
    assert r.status_code == 200
    s = r.json()
    assert s["count"] == 3
    assert s["min"] == 10
    assert s["max"] == 30
    assert s["avg"] == 20
    assert s["latest_value"] == 30
    assert s["sensor"] is None


def test_device_stats_can_be_limited_to_one_sensor(client):
    client.post("/readings", json=make_reading(sensor="temperature", value=20))
    client.post("/readings", json=make_reading(sensor="humidity", value=60, unit="%"))

    s = client.get("/devices/esp32-01/stats", params={"sensor": "humidity"}).json()
    assert s["count"] == 1
    assert s["avg"] == 60
    assert s["sensor"] == "humidity"


def test_device_stats_unknown_device_returns_404(client):
    assert client.get("/devices/nope/stats").status_code == 404


def test_device_stats_unknown_sensor_returns_404(client):
    client.post("/readings", json=make_reading())
    assert client.get("/devices/esp32-01/stats", params={"sensor": "pressure"}).status_code == 404


# ---------- persistence ----------

def test_data_persists_between_requests(client):
    client.post("/readings", json=make_reading(value=7))
    client.post("/readings", json=make_reading(value=8))
    assert len(client.get("/readings").json()) == 2
