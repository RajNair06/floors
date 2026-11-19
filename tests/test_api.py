"""Tests for API endpoints."""

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)

VALID_PLAN = {
    "schema_version": "1.0",
    "id": "test_01",
    "units": "m",
    "ceiling_height": 2.7,
    "rooms": [
        {"id": "r1", "type": "living", "name": "Living room", "x": 0, "y": 0, "w": 5.0, "h": 4.0},
        {"id": "r2", "type": "bedroom", "name": "Bedroom 1", "x": 5.0, "y": 0, "w": 3.5, "h": 4.0},
    ],
    "doors": [
        {"id": "d1", "from": "r1", "to": "outside", "wall": "S", "offset": 1.0, "width": 1.0},
        {"id": "d2", "from": "r1", "to": "r2", "wall": "E", "offset": 1.5, "width": 0.9},
    ],
    "windows": [
        {"id": "w1", "room": "r1", "wall": "N", "offset": 1.0, "width": 1.5},
        {"id": "w2", "room": "r2", "wall": "N", "offset": 0.5, "width": 1.2},
    ],
}


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_schema():
    resp = client.get("/api/schema")
    assert resp.status_code == 200
    body = resp.json()
    assert "schema" in body
    assert "rules" in body


def test_validate_pass():
    resp = client.post("/api/validate", json=VALID_PLAN)
    assert resp.status_code == 200
    assert resp.json()["passed"] is True


def test_validate_schema_error():
    bad = dict(VALID_PLAN)
    bad["doors"] = [{"id": "d1", "from": "r1", "to": "r99", "wall": "S", "offset": 1.0, "width": 1.0}]
    resp = client.post("/api/validate", json=bad)
    assert resp.status_code == 422


def test_score():
    resp = client.post("/api/score", json=VALID_PLAN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert body["score"] == 1.0


def test_render():
    resp = client.post("/api/render", json=VALID_PLAN)
    assert resp.status_code == 200
    assert "<svg" in resp.json()["svg"]


def test_eval():
    resp = client.post("/api/eval", json={"plans": [VALID_PLAN, VALID_PLAN]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["n"] == 2
    assert body["pass_rate"] == 1.0
