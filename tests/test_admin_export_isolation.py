from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_admin_export_isolation():
    # 1. Register Org A and Admin A
    org_a = f"org-a-{datetime.now(timezone.utc).timestamp()}"
    reg_a = client.post(
        "/auth/register",
        json={"org_name": org_a, "username": "admin_a", "password": "password123"},
    )
    assert reg_a.status_code == 201

    # Login Admin A
    login_a = client.post(
        "/auth/login",
        json={"org_name": org_a, "username": "admin_a", "password": "password123"},
    )
    assert login_a.status_code == 200
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create Room A in Org A
    room_a = client.post(
        "/rooms",
        json={"name": "Room A", "capacity": 10, "hourly_rate_cents": 1000},
        headers=headers_a,
    )
    assert room_a.status_code == 201
    room_a_id = room_a.json()["id"]

    # 2. Register Org B and Admin B
    org_b = f"org-b-{datetime.now(timezone.utc).timestamp()}"
    reg_b = client.post(
        "/auth/register",
        json={"org_name": org_b, "username": "admin_b", "password": "password123"},
    )
    assert reg_b.status_code == 201

    # Login Admin B
    login_b = client.post(
        "/auth/login",
        json={"org_name": org_b, "username": "admin_b", "password": "password123"},
    )
    assert login_b.status_code == 200
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create Room B in Org B
    room_b = client.post(
        "/rooms",
        json={"name": "Room B", "capacity": 5, "hourly_rate_cents": 1500},
        headers=headers_b,
    )
    assert room_b.status_code == 201
    room_b_id = room_b.json()["id"]

    # 3. Request Org B's Room B export using Admin A's token
    export_res = client.get(
        f"/admin/export?room_id={room_b_id}",
        headers=headers_a,
    )

    # 4. Assert response is 404 ROOM_NOT_FOUND
    assert export_res.status_code == 404, f"Expected 404 but got {export_res.status_code} with body: {export_res.text}"
    assert export_res.json()["code"] == "ROOM_NOT_FOUND"

    print("\n--- TEST PASSED SUCCESSFULLY ---")
    print(f"Admin A attempted to export Room B (ID: {room_b_id}).")
    print(f"Response status: {export_res.status_code}")
    print(f"Response JSON: {export_res.json()}")
    print("Cross-tenant data leak is verified as permanently plugged!")
