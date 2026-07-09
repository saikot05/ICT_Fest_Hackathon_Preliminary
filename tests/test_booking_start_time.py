"""Regression test for booking start_time serialization."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup_user_and_room():
    org = f"start-time-org-{datetime.now().timestamp()}"

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
        json={"name": "Start Time Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    return headers, room_id


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_get_booking_returns_original_start_time():
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    requested_start = now + timedelta(hours=3)
    requested_end = now + timedelta(hours=4)

    create_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(requested_start),
            "end_time": _iso_utc(requested_end),
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    booking_id = create_response.json()["id"]

    get_response = client.get(f"/bookings/{booking_id}", headers=headers)
    assert get_response.status_code == 200

    payload = get_response.json()
    response_start = datetime.fromisoformat(payload["start_time"].replace("Z", "+00:00"))
    expected_start = requested_start.replace(tzinfo=timezone.utc)
    assert response_start == expected_start
    assert payload["start_time"] != payload["created_at"]
