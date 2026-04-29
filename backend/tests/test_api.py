from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_snapshot_endpoint_returns_operations_payload() -> None:
    with TestClient(app) as client:
        response = client.get("/api/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert {"timestamp", "machine", "telemetry", "oee", "losses", "financialImpact", "anomalies", "insight"} <= set(payload)


def test_websocket_emits_operations_payload() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            payload = websocket.receive_json()

    assert "oee" in payload
    assert "losses" in payload
