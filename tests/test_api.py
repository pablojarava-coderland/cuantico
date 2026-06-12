"""Pruebas de humo de la API HTTP: wiring, serialización y mapeo de errores."""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import build_app
from tests.conftest import FakeClock

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed.json"


@pytest.fixture
def client() -> TestClient:
    app = build_app(seed_path=SEED_PATH, clock=FakeClock())
    return TestClient(app)


def test_health_exposes_seed_warnings(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(response.json()["seed_warnings"]) > 0


def test_create_and_cancel_full_refund_via_http(client):
    # u-diana no tiene reservas activas en el seed (la suya está cancelada).
    response = client.post(
        "/reservations",
        json={
            "user_id": "u-diana",
            "service_id": "svc-corte",
            "start": "2026-06-18T10:00:00-05:00",
        },
    )
    assert response.status_code == 201, response.text
    reservation_id = response.json()["id"]

    response = client.post(f"/reservations/{reservation_id}/cancel")
    assert response.status_code == 200, response.text
    body = response.json()
    # >24h de anticipación, plan standard: reembolso del 100%.
    assert body["policy"] == "standard"
    assert Decimal(str(body["refund_amount"])) == Decimal("40000.00")
    assert body["reservation"]["status"] == "cancelled"


def test_create_on_sunday_returns_409_with_domain_error(client):
    response = client.post(
        "/reservations",
        json={
            "user_id": "u-diana",
            "service_id": "svc-corte",
            "start": "2026-06-21T10:00:00-05:00",  # domingo
        },
    )
    assert response.status_code == 409
    assert response.json()["error"] == "closed_day"


def test_unknown_user_returns_404(client):
    response = client.get("/users/no-existe/reservations")
    assert response.status_code == 404
    assert response.json()["error"] == "user_not_found"


def test_list_reservations_with_range(client):
    response = client.get(
        "/users/u-ana/reservations",
        params={"from": "2026-06-19T00:00:00-05:00", "to": "2026-06-19T23:59:00-05:00"},
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert ids == ["r-001"]
