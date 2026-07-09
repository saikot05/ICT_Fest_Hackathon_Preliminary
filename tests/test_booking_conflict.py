"""Tests for booking conflict behavior."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup_user_and_room():
    org = f"conflict-org-{datetime.now().timestamp()}"

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
        json={"name": "Conflict Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    return headers, room_id


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_back_to_back_booking_succeeds():
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    first_start = now + timedelta(hours=2)
    first_end = now + timedelta(hours=3)
    second_start = now + timedelta(hours=3)
    second_end = now + timedelta(hours=4)

    first_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(first_start),
            "end_time": _iso_utc(first_end),
        },
        headers=headers,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(second_start),
            "end_time": _iso_utc(second_end),
        },
        headers=headers,
    )

    assert second_response.status_code == 201


def test_overlapping_booking_fails_with_room_conflict():
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    first_start = now + timedelta(hours=2)
    first_end = now + timedelta(hours=3)
    second_start = now + timedelta(hours=2, minutes=30)
    second_end = now + timedelta(hours=3, minutes=30)

    first_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(first_start),
            "end_time": _iso_utc(first_end),
        },
        headers=headers,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(second_start),
            "end_time": _iso_utc(second_end),
        },
        headers=headers,
    )

    assert second_response.status_code == 409
    assert second_response.json()["code"] == "ROOM_CONFLICT"
