"""Regression tests for cache invalidation on booking create/cancel."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import cache
from app.main import app

client = TestClient(app)


def _setup_user_and_room():
    org = f"cache-org-{datetime.now().timestamp()}"

    reg = client.post(
        "/auth/register",
        json={"org_name": org, "username": "testuser", "password": "pw12345"},
    )
    assert reg.status_code == 201
    org_id = reg.json()["org_id"]

    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "testuser", "password": "pw12345"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    room = client.post(
        "/rooms",
        json={"name": "Cache Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    return headers, room_id, org_id


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_booking_creation_invalidates_availability_and_report_cache():
    headers, room_id, org_id = _setup_user_and_room()
    cache.set_availability(room_id, "2026-01-01", {"cached": True})
    cache.set_report(org_id, "2026-01-01", "2026-01-31", {"cached": True})

    now = datetime.utcnow()
    start = now + timedelta(hours=2)
    end = now + timedelta(hours=3)
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
    assert cache.get_availability(room_id, start.date().isoformat()) is None


def test_booking_cancellation_invalidates_report_cache():
    headers, room_id, org_id = _setup_user_and_room()
    cache.set_report(org_id, "2026-01-01", "2026-01-31", {"cached": True})

    now = datetime.utcnow()
    start = now + timedelta(hours=2)
    end = now + timedelta(hours=3)
    create_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(start),
            "end_time": _iso_utc(end),
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    booking_id = create_response.json()["id"]

    cancel_response = client.post(f"/bookings/{booking_id}/cancel", headers=headers)

    assert cancel_response.status_code == 200
    assert cache.get_report(org_id, "2026-01-01", "2026-01-31") is None
