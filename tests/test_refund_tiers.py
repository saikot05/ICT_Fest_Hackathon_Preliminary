"""Regression tests for refund notice period tiers."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup_user_and_room():
    org = f"refund-org-{datetime.now().timestamp()}"

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
        json={"name": "Refund Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    return headers, room_id


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _create_booking(headers: dict, room_id: int, start_offset_hours: int, now: datetime):
    start = now + timedelta(hours=start_offset_hours)
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


def test_refund_is_100_percent_at_exactly_48_hours(monkeypatch):
    frozen_now = datetime(2026, 1, 1, 12, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen_now

    monkeypatch.setattr("app.routers.bookings.datetime", FrozenDateTime)

    headers, room_id = _setup_user_and_room()
    booking_id = _create_booking(headers, room_id, 48, frozen_now)

    response = client.post(f"/bookings/{booking_id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["refund_percent"] == 100


def test_refund_is_50_percent_at_25_hours(monkeypatch):
    frozen_now = datetime(2026, 1, 1, 12, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen_now

    monkeypatch.setattr("app.routers.bookings.datetime", FrozenDateTime)

    headers, room_id = _setup_user_and_room()
    booking_id = _create_booking(headers, room_id, 25, frozen_now)

    response = client.post(f"/bookings/{booking_id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["refund_percent"] == 50


def test_refund_is_0_percent_at_23_hours(monkeypatch):
    frozen_now = datetime(2026, 1, 1, 12, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen_now

    monkeypatch.setattr("app.routers.bookings.datetime", FrozenDateTime)

    headers, room_id = _setup_user_and_room()
    booking_id = _create_booking(headers, room_id, 23, frozen_now)

    response = client.post(f"/bookings/{booking_id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["refund_percent"] == 0
