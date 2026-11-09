"""/predict-from-csv."""

from __future__ import annotations

_COLUMNS = (
    "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,latitude,longitude"
)


def _csv(rows: list[str], header: str = _COLUMNS) -> bytes:
    return (header + "\n" + "\n".join(rows)).encode("utf-8")


def test_wrong_extension(client):
    r = client.post(
        "/predict-from-csv",
        files={"file": ("x.txt", b"abc", "text/plain")},
    )
    assert r.status_code == 400


def test_invalid_csv(client):
    r = client.post(
        "/predict-from-csv",
        files={"file": ("x.csv", b"\x00\xff", "text/csv")},
    )
    assert r.status_code == 400


def test_empty_csv(client):
    r = client.post(
        "/predict-from-csv",
        files={"file": ("x.csv", b"", "text/csv")},
    )
    assert r.status_code == 400


def test_missing_features(client_with_model):
    r = client_with_model.post(
        "/predict-from-csv",
        files={"file": ("x.csv", _csv(["1,2"], header="a,b"), "text/csv")},
    )
    assert r.status_code == 422


def test_no_model(client):
    r = client.post(
        "/predict-from-csv",
        files={"file": ("x.csv", _csv(["10,5,0,5,52.5,13.4"]), "text/csv")},
    )
    assert r.status_code == 503


def test_success_no_target(client_with_model):
    body = _csv(["10,5,0,5,52.5,13.4", "12,6,2,8,52.5,13.4"])
    r = client_with_model.post(
        "/predict-from-csv",
        files={"file": ("x.csv", body, "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["roc_auc"] is None
    assert data["rows_count"] == 2
    assert "predicted_rain_tomorrow" in data["data"][0]


def test_success_with_target(client_with_model):
    header = _COLUMNS + ",rain_tomorrow"
    body = _csv(["10,5,0,5,52.5,13.4,0", "12,6,2,8,52.5,13.4,1"], header=header)
    r = client_with_model.post(
        "/predict-from-csv",
        files={"file": ("x.csv", body, "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["roc_auc"] == 0.5
