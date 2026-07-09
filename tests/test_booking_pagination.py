"""Tests for booking list ordering and pagination."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _setup_user_and_room():
    org = f"pagination-org-{datetime.now().timestamp()}"

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
        json={"name": "Pagination Room", "capacity": 4, "hourly_rate_cents": 1000},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    return headers, room_id


def _iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def test_list_bookings_is_sorted_and_paged_correctly():
    headers, room_id = _setup_user_and_room()

    now = datetime.utcnow()
    bookings = [
        (now + timedelta(hours=4), now + timedelta(hours=5)),
        (now + timedelta(hours=2), now + timedelta(hours=3)),
        (now + timedelta(hours=1), now + timedelta(hours=2)),
    ]

    created_ids = []
    for start, end in bookings:
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
        created_ids.append((start, response.json()["id"]))

    page1 = client.get("/bookings?page=1&limit=2", headers=headers)
    assert page1.status_code == 200
    page1_data = page1.json()
    assert page1_data["page"] == 1
    assert page1_data["limit"] == 2
    assert page1_data["total"] == 3

    page1_ids = [item["id"] for item in page1_data["items"]]
    assert page1_ids == sorted(page1_ids, key=lambda item_id: next(
        booking["start_time"] for booking in page1_data["items"] if booking["id"] == item_id
    ))

    page2 = client.get("/bookings?page=2&limit=2", headers=headers)
    assert page2.status_code == 200
    page2_data = page2.json()
    page2_ids = [item["id"] for item in page2_data["items"]]

    expected_ids = [booking_id for _, booking_id in sorted(created_ids, key=lambda item: item[0])][2:]
    assert page2_ids == expected_ids
    assert page1_ids[0] != page2_ids[0]
