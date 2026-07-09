from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(
        minute=0, second=0, microsecond=0
    ).isoformat()

def test_room_stats_consistency():
    client = TestClient(app)
    
    # 1. Create org and register user
    org = f"test-org-{datetime.now().timestamp()}"
    reg = client.post(
        "/auth/register",
        json={"org_name": org, "username": "bob", "password": "pw12345"},
    )
    assert reg.status_code == 201, reg.text
    
    # Login to get token
    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "bob", "password": "pw12345"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create room
    room = client.post(
        "/rooms",
        json={"name": "Conference Room A", "capacity": 10, "hourly_rate_cents": 1500},
        headers=headers,
    )
    assert room.status_code == 201, room.text
    room_id = room.json()["id"]
    
    # Verify initial stats (should be 0, 0)
    stats_before = client.get(f"/rooms/{room_id}/stats", headers=headers)
    assert stats_before.status_code == 200, stats_before.text
    assert stats_before.json() == {
        "room_id": room_id,
        "total_confirmed_bookings": 0,
        "total_revenue_cents": 0
    }
    print("Initial stats verification passed: 0 confirmed bookings, 0 revenue.")
    
    # 3. Create a booking (2 hours)
    booking = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": _future(50), "end_time": _future(52)},
        headers=headers,
    )
    assert booking.status_code == 201, booking.text
    booking_id = booking.json()["id"]
    expected_revenue = 1500 * 2 # 3000 cents
    assert booking.json()["price_cents"] == expected_revenue
    
    # Verify stats after booking
    stats_after_booking = client.get(f"/rooms/{room_id}/stats", headers=headers)
    assert stats_after_booking.status_code == 200, stats_after_booking.text
    assert stats_after_booking.json() == {
        "room_id": room_id,
        "total_confirmed_bookings": 1,
        "total_revenue_cents": expected_revenue
    }
    print(f"Stats verification after booking passed: 1 confirmed booking, {expected_revenue} cents revenue.")
    
    # 4. Cancel the booking
    cancel = client.post(f"/bookings/{booking_id}/cancel", headers=headers)
    assert cancel.status_code == 200, cancel.text
    
    # Verify stats after cancellation
    stats_after_cancel = client.get(f"/rooms/{room_id}/stats", headers=headers)
    assert stats_after_cancel.status_code == 200, stats_after_cancel.text
    assert stats_after_cancel.json() == {
        "room_id": room_id,
        "total_confirmed_bookings": 0,
        "total_revenue_cents": 0
    }
    print("Stats verification after cancellation passed: 0 confirmed bookings, 0 revenue.")
    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_room_stats_consistency()
