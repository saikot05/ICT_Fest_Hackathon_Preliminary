"""Tests for booking visibility and ownership checks."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_and_login(username: str, org_name: str):
    reg = client.post(
        "/auth/register",
        json={"org_name": org_name, "username": username, "password": "pw12345"},
    )
    assert reg.status_code == 201

    login = client.post(
        "/auth/login",
        json={"org_name": org_name, "username": username, "password": "pw12345"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_room(headers: dict):
    room = client.post(
        "/rooms",
        json={"name": "Visibility Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    return room.json()["id"]


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_member_cannot_read_another_members_booking():
    org_name = f"visibility-org-{datetime.now().timestamp()}"
    member_a_headers = _register_and_login("member-a", org_name)
    member_b_headers = _register_and_login("member-b", org_name)
    room_id = _create_room(member_a_headers)

    now = datetime.utcnow()
    start = now + timedelta(hours=2)
    end = now + timedelta(hours=3)
    booking_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(start),
            "end_time": _iso_utc(end),
        },
        headers=member_a_headers,
    )
    assert booking_response.status_code == 201
    booking_id = booking_response.json()["id"]

    response = client.get(f"/bookings/{booking_id}", headers=member_b_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "BOOKING_NOT_FOUND"


def test_member_can_read_own_booking_and_admin_can_read_others():
    org_name = f"visibility-org-admin-{datetime.now().timestamp()}"
    admin_headers = _register_and_login("admin", org_name)
    member_headers = _register_and_login("member", org_name)
    room_id = _create_room(admin_headers)

    now = datetime.utcnow()
    start = now + timedelta(hours=2)
    end = now + timedelta(hours=3)
    booking_response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(start),
            "end_time": _iso_utc(end),
        },
        headers=member_headers,
    )
    assert booking_response.status_code == 201
    booking_id = booking_response.json()["id"]

    own_response = client.get(f"/bookings/{booking_id}", headers=member_headers)
    assert own_response.status_code == 200

    admin_response = client.get(f"/bookings/{booking_id}", headers=admin_headers)
    assert admin_response.status_code == 200
