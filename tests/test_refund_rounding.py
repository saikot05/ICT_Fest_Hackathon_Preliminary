"""Regression tests for refund amount rounding."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup_user_and_room(hourly_rate_cents: int):
    org = f"refund-rounding-org-{datetime.now().timestamp()}"

    reg = client.post(
        "/auth/register",
        json={"org_name": org, "username": "testuser", "password": "pw12345"},
    )
    assert reg.status_code == 201

    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "testuser", "password": "pw12345"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    room = client.post(
        "/rooms",
        json={"name": "Refund Rounding Room", "capacity": 4, "hourly_rate_cents": hourly_rate_cents},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    return headers, room_id


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _create_booking(headers: dict, room_id: int, price_cents: int):
    now = datetime.utcnow()
    start = now + timedelta(hours=48)
    end = start + timedelta(hours=1)
    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(start),
            "end_time": _iso_utc(end),
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_half_cents_round_up_for_50_percent_refund():
    headers, room_id = _setup_user_and_room(1001)
    booking_id = _create_booking(headers, room_id, 1001)

    response = client.post(f"/bookings/{booking_id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["refund_amount_cents"] == 501


def test_even_cents_stay_exact_for_50_percent_refund():
    headers, room_id = _setup_user_and_room(1000)
    booking_id = _create_booking(headers, room_id, 1000)

    response = client.post(f"/bookings/{booking_id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["refund_amount_cents"] == 500
