from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(
        minute=0, second=0, microsecond=0
    ).isoformat()

def test_timezone_conversion():
    # Helper to check timezone parse
    from app.timeutils import parse_input_datetime
    # A time with +06:00 offset
    value = "2026-07-09T19:44:58+06:00"
    dt = parse_input_datetime(value)
    # 19:44:58 +06:00 should be converted to 13:44:58 UTC
    assert dt.hour == 13
    assert dt.minute == 44
    assert dt.second == 58

def test_registration_conflict_and_auth():
    org = f"acme-test-{datetime.now().timestamp()}"
    # Register admin
    r1 = client.post(
        "/auth/register",
        json={"org_name": org, "username": "owner", "password": "password123"},
    )
    assert r1.status_code == 201
    
    # Try register again with same username in same org (should fail 409)
    r2 = client.post(
        "/auth/register",
        json={"org_name": org, "username": "owner", "password": "newpassword"},
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "USERNAME_TAKEN"

    # Login to verify access token and token exp - iat
    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "owner", "password": "password123"},
    )
    assert login.status_code == 200
    token_data = login.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    import jwt
    from app.config import JWT_SECRET, JWT_ALGORITHM
    decoded = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    # exp - iat must be exactly 900 seconds
    assert decoded["exp"] - decoded["iat"] == 900

    # Test Logout Revocation
    headers = {"Authorization": f"Bearer {access_token}"}
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    # Subsequent use should fail
    subsequent = client.get("/rooms", headers=headers)
    assert subsequent.status_code == 401

    # Test Refresh Token Single-Use
    refresh1 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh1.status_code == 200
    new_refresh_token = refresh1.json()["refresh_token"]

    # Reusing the old refresh token should fail with 401
    refresh2 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh2.status_code == 401

def test_booking_rules_and_refunds():
    org = f"org-booking-{datetime.now().timestamp()}"
    # Register admin
    reg_admin = client.post(
        "/auth/register",
        json={"org_name": org, "username": "admin_user", "password": "password123"},
    )
    admin_token = client.post(
        "/auth/login",
        json={"org_name": org, "username": "admin_user", "password": "password123"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Register member
    reg_member = client.post(
        "/auth/register",
        json={"org_name": org, "username": "member_user", "password": "password123"},
    )
    member_token = client.post(
        "/auth/login",
        json={"org_name": org, "username": "member_user", "password": "password123"},
    ).json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Create Room
    # hourly rate = 1001 cents to test half-cents rounding up (50% of 1001 is 500.5, rounded to 501)
    room = client.post(
        "/rooms",
        json={"name": "Deluxe Suite", "capacity": 5, "hourly_rate_cents": 1001},
        headers=admin_headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    # 1. Booking duration check: 0 hours should fail
    start_time = _future(10)
    end_time = start_time
    b_fail = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": start_time, "end_time": end_time},
        headers=member_headers,
    )
    assert b_fail.status_code == 400

    # 2. Booking past check: in the past should fail
    past_start = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    past_end = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    b_past = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": past_start, "end_time": past_end},
        headers=member_headers,
    )
    assert b_past.status_code == 400

    # 3. Create normal booking (1 hour)
    b1_start = _future(26)  # 26 hours from now (to guarantee > 24 hours notice when cancelled)
    b1_end = _future(27)
    b1 = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": b1_start, "end_time": b1_end},
        headers=member_headers,
    )
    assert b1.status_code == 201
    b1_id = b1.json()["id"]
    assert b1.json()["price_cents"] == 1001

    # 4. Check back-to-back booking overlap:
    # A booking starting exactly when b1 ends should succeed
    b2_start = b1_end
    b2_end = _future(28)
    b2 = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": b2_start, "end_time": b2_end},
        headers=member_headers,
    )
    assert b2.status_code == 201

    # An overlapping booking should fail (e.g. starts 24:30, ends 25:30)
    b3_start = (datetime.fromisoformat(b1_start) + timedelta(minutes=30)).isoformat()
    b3_end = (datetime.fromisoformat(b1_end) + timedelta(minutes=30)).isoformat()
    b3 = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": b3_start, "end_time": b3_end},
        headers=member_headers,
    )
    assert b3.status_code == 409

    # 5. Member Visibility check: member reading another member's booking in different org (or same org but not own)
    # Let's create another member in a different org
    other_org = f"other-{datetime.now().timestamp()}"
    client.post(
        "/auth/register",
        json={"org_name": other_org, "username": "other_user", "password": "password123"},
    )
    other_token = client.post(
        "/auth/login",
        json={"org_name": other_org, "username": "other_user", "password": "password123"},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Reading b1 (from other org) should return 404
    read_other = client.get(f"/bookings/{b1_id}", headers=other_headers)
    assert read_other.status_code == 404

    # 6. Cancellation and refund rounding:
    # Cancel b1 (starts in 24 hours, so notice is 24 hours -> 50% refund)
    cancel = client.post(f"/bookings/{b1_id}/cancel", headers=member_headers)
    assert cancel.status_code == 200
    res = cancel.json()
    assert res["refund_percent"] == 50
    # 50% of 1001 = 500.5 cents -> rounded up to 501
    assert res["refund_amount_cents"] == 501

    # Check that RefundLog entry has same amount
    get_b = client.get(f"/bookings/{b1_id}", headers=member_headers)
    assert get_b.status_code == 200
    assert get_b.json()["refunds"][0]["amount_cents"] == 501

def test_admin_cross_org_export():
    # Register org A
    org_a = f"org-a-{datetime.now().timestamp()}"
    client.post(
        "/auth/register",
        json={"org_name": org_a, "username": "admin_a", "password": "password123"},
    )
    token_a = client.post(
        "/auth/login",
        json={"org_name": org_a, "username": "admin_a", "password": "password123"},
    ).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register org B
    org_b = f"org-b-{datetime.now().timestamp()}"
    client.post(
        "/auth/register",
        json={"org_name": org_b, "username": "admin_b", "password": "password123"},
    )
    token_b = client.post(
        "/auth/login",
        json={"org_name": org_b, "username": "admin_b", "password": "password123"},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create room in Org B
    room_b = client.post(
        "/rooms",
        json={"name": "Room B", "capacity": 5, "hourly_rate_cents": 1000},
        headers=headers_b,
    )
    room_b_id = room_b.json()["id"]

    # Export room_b from Admin A should return 404 ROOM_NOT_FOUND
    export_leak = client.get(f"/admin/export?room_id={room_b_id}", headers=headers_a)
    assert export_leak.status_code == 404
