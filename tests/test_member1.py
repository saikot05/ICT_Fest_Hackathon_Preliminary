from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.timeutils import parse_input_datetime

client = TestClient(app)

def test_timezone_conversion():
    # Input has offset +06:00. In UTC it should be 6 hours earlier.
    dt_with_offset = "2026-07-09T18:00:00+06:00"
    parsed = parse_input_datetime(dt_with_offset)
    # 18:00 +06:00 is 12:00 UTC
    assert parsed == datetime(2026, 7, 9, 12, 0, 0)

    # Naive input treated as UTC
    dt_naive = "2026-07-09T18:00:00"
    parsed_naive = parse_input_datetime(dt_naive)
    assert parsed_naive == datetime(2026, 7, 9, 18, 0, 0)


def test_duplicate_registration_error():
    org = f"member1-org-{datetime.now().timestamp()}"
    
    # First registration
    res1 = client.post(
        "/auth/register",
        json={"org_name": org, "username": "bob", "password": "password123"}
    )
    assert res1.status_code == 201

    # Second registration with same username in same org
    res2 = client.post(
        "/auth/register",
        json={"org_name": org, "username": "bob", "password": "password456"}
    )
    assert res2.status_code == 409
    assert res2.json()["code"] == "USERNAME_TAKEN"


def test_logout_token_revocation_and_refresh_rotation():
    org = f"member1-org2-{datetime.now().timestamp()}"
    
    # Register and Login
    client.post(
        "/auth/register",
        json={"org_name": org, "username": "charlie", "password": "password123"}
    )
    login = client.post(
        "/auth/login",
        json={"org_name": org, "username": "charlie", "password": "password123"}
    )
    assert login.status_code == 200
    res_json = login.json()
    access_token = res_json["access_token"]
    refresh_token = res_json["refresh_token"]

    # Access endpoint with valid token
    headers = {"Authorization": f"Bearer {access_token}"}
    res_rooms = client.get("/rooms", headers=headers)
    assert res_rooms.status_code == 200

    # Logout
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    # Access endpoint with revoked token -> 401
    res_rooms_revoked = client.get("/rooms", headers=headers)
    assert res_rooms_revoked.status_code == 401
    assert res_rooms_revoked.json()["detail"] == "Token has been revoked"

    # Test Refresh Token Single-Use (Rotation)
    # First refresh call -> 200
    refresh1 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh1.status_code == 200
    new_tokens = refresh1.json()
    new_access_token = new_tokens["access_token"]
    new_refresh_token = new_tokens["refresh_token"]

    # Second refresh call with same old refresh token -> 401
    refresh2 = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh2.status_code == 401
    assert refresh2.json()["detail"] == "Token has been revoked"

    # Access endpoint with new access token -> 200
    headers_new = {"Authorization": f"Bearer {new_access_token}"}
    res_rooms_new = client.get("/rooms", headers=headers_new)
    assert res_rooms_new.status_code == 200
