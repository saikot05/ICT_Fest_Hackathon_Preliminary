"""Test booking window validation — strict future enforcement."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup_user_and_room():
    """Helper to create a user, login, and create a room."""
    org = f"test-org-{datetime.now().timestamp()}"
    
    # Register
    reg = client.post(
        "/auth/register",
        json={"org_name": org, "username": "testuser", "password": "pw12345"},
    )
    assert reg.status_code == 201
    
    # Login
    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "testuser", "password": "pw12345"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create room
    room = client.post(
        "/rooms",
        json={"name": "Test Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]
    
    return headers, room_id


def _iso_utc(dt: datetime) -> str:
    """Convert datetime to ISO 8601 UTC string."""
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_booking_with_past_start_time_fails():
    """Booking with start_time in the past should fail with 400 INVALID_BOOKING_WINDOW."""
    headers, room_id = _setup_user_and_room()
    
    # Create times: start in the past, end in the future
    now = datetime.utcnow()
    past_start = now - timedelta(hours=1)
    future_end = now + timedelta(hours=2)
    
    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(past_start),
            "end_time": _iso_utc(future_end),
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_BOOKING_WINDOW"
    assert "start_time must be in the future" in data["detail"]


def test_booking_with_exact_now_fails():
    """Booking with start_time equal to now should fail with 400 INVALID_BOOKING_WINDOW."""
    headers, room_id = _setup_user_and_room()
    
    # Create times: start at exactly now
    now = datetime.utcnow()
    end = now + timedelta(hours=1)
    
    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(now),
            "end_time": _iso_utc(end),
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_BOOKING_WINDOW"
    assert "start_time must be in the future" in data["detail"]


def test_booking_with_end_time_not_after_start_time_fails():
    """Booking with end_time equal to start_time should fail with 400 INVALID_BOOKING_WINDOW."""
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    future_start = now + timedelta(hours=2)

    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(future_start),
            "end_time": _iso_utc(future_start),
        },
        headers=headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_BOOKING_WINDOW"
    assert "end_time must be after start_time" in data["detail"]


def test_booking_with_less_than_one_hour_duration_fails():
    """Booking with duration less than 1 hour should fail with 400 INVALID_BOOKING_WINDOW."""
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    future_start = now + timedelta(hours=2)
    future_end = now + timedelta(hours=2, minutes=30)

    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(future_start),
            "end_time": _iso_utc(future_end),
        },
        headers=headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_BOOKING_WINDOW"
    assert "duration" in data["detail"].lower()


def test_booking_with_valid_duration_between_one_and_eight_hours_succeeds():
    """Booking with a valid 2-hour window should succeed with 201."""
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    future_start = now + timedelta(hours=2)
    future_end = now + timedelta(hours=4)

    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _iso_utc(future_start),
            "end_time": _iso_utc(future_end),
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "confirmed"
    assert "price_cents" in data
