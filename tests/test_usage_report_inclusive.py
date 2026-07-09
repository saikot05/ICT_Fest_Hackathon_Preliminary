from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_usage_report_inclusive():
    # 1. Register Admin and Org
    org = f"acme-report-{datetime.now(timezone.utc).timestamp()}"
    reg = client.post(
        "/auth/register",
        json={"org_name": org, "username": "admin_user", "password": "password123"},
    )
    assert reg.status_code == 201

    # Login to get token
    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "admin_user", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Room
    room = client.post(
        "/rooms",
        json={"name": "Conference Room X", "capacity": 8, "hourly_rate_cents": 1200},
        headers=headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    # 2. Create a confirmed booking for tomorrow at 14:00 UTC (strictly in the future)
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    tomorrow_str = tomorrow.date().isoformat()
    day_after_str = (tomorrow + timedelta(days=1)).date().isoformat()

    # We book tomorrow from 14:00 to 16:00 UTC
    start_time = datetime.combine(tomorrow.date(), datetime.strptime("14:00:00", "%H:%M:%S").time(), tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=2)

    booking = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        headers=headers,
    )
    assert booking.status_code == 201, f"Failed to create booking: {booking.text}"

    # 3. Hit usage report with tomorrow's date range (should return 1 booking)
    report_tomorrow = client.get(
        f"/admin/usage-report?from={tomorrow_str}&to={tomorrow_str}",
        headers=headers,
    )
    assert report_tomorrow.status_code == 200, report_tomorrow.text
    rooms_data = report_tomorrow.json()["rooms"]
    assert len(rooms_data) == 1
    assert rooms_data[0]["confirmed_bookings"] == 1
    assert rooms_data[0]["revenue_cents"] == 2400

    # 4. Hit usage report with the day after tomorrow's date range (should return 0 bookings)
    report_day_after = client.get(
        f"/admin/usage-report?from={day_after_str}&to={day_after_str}",
        headers=headers,
    )
    assert report_day_after.status_code == 200, report_day_after.text
    rooms_day_after_data = report_day_after.json()["rooms"]
    assert len(rooms_day_after_data) == 1
    assert rooms_day_after_data[0]["confirmed_bookings"] == 0
    assert rooms_day_after_data[0]["revenue_cents"] == 0

    print("\n--- TEST PASSED SUCCESSFULLY ---")
    print(f"Usage report queried for {tomorrow_str} to {tomorrow_str} correctly returned 1 confirmed booking.")
    print(f"Usage report queried for {day_after_str} to {day_after_str} correctly returned 0 confirmed bookings.")
