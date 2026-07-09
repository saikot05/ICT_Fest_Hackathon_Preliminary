import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ratelimit_concurrency():
    # 1. Register Org & Admin (first user is admin)
    org = f"acme-rate-{datetime.now(timezone.utc).timestamp()}"
    reg_admin = client.post(
        "/auth/register",
        json={"org_name": org, "username": "admin_user", "password": "password123"},
    )
    assert reg_admin.status_code == 201

    # Login Admin
    admin_token = client.post(
        "/auth/login",
        json={"org_name": org, "username": "admin_user", "password": "password123"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Register Member (second user is member)
    reg_member = client.post(
        "/auth/register",
        json={"org_name": org, "username": "member_user", "password": "password123"},
    )
    assert reg_member.status_code == 201

    # Login Member
    login_member = client.post(
        "/auth/login",
        json={"org_name": org, "username": "member_user", "password": "password123"},
    )
    assert login_member.status_code == 200
    token = login_member.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Room
    room = client.post(
        "/rooms",
        json={"name": "Rate Limit Room", "capacity": 5, "hourly_rate_cents": 1000},
        headers=admin_headers,
    )
    assert room.status_code == 201
    room_id = room.json()["id"]

    # 2. Fire 30 concurrent booking creation requests
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    end_time = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0).isoformat()

    num_requests = 30
    results = []

    def make_request():
        return client.post(
            "/bookings",
            json={
                "room_id": room_id,
                "start_time": start_time,
                "end_time": end_time,
            },
            headers=headers,
        )

    # Use ThreadPoolExecutor to fire requests concurrently
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    # 3. Analyze status codes
    rate_limited_count = 0
    non_rate_limited_count = 0

    for r in results:
        if r.status_code == 429:
            assert r.json()["code"] == "RATE_LIMITED"
            rate_limited_count += 1
        elif r.status_code in [201, 400, 409]:
            non_rate_limited_count += 1
        else:
            # Output unexpected responses
            print(f"Unexpected status code {r.status_code}: {r.text}")

    print("\n--- TEST PASSED SUCCESSFULLY ---")
    print(f"Fired {num_requests} concurrent booking requests.")
    print(f"Requests passed (201/409): {non_rate_limited_count} (Expected: 20)")
    print(f"Requests blocked (429 RATE_LIMITED): {rate_limited_count} (Expected: 10)")
    
    assert non_rate_limited_count == 20, f"Expected 20 non-rate-limited requests, got {non_rate_limited_count}"
    assert rate_limited_count == 10, f"Expected 10 rate-limited requests, got {rate_limited_count}"
