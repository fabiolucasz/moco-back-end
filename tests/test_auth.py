import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient) -> None:
    """Verifies successful registration of a new user."""
    payload = {
        "email": "test.user@finpilot.com",
        "password": "Password123!",
        "full_name": "Test FinPilot User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test.user@finpilot.com"
    assert data["full_name"] == "Test FinPilot User"
    assert data["is_active"] is True
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(client: AsyncClient) -> None:
    """Verifies that duplicate registration returns HTTP 409 Conflict."""
    payload = {
        "email": "duplicate@finpilot.com",
        "password": "Password123!",
        "full_name": "First User",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_invalid_payload(client: AsyncClient) -> None:
    """Verifies validation error for invalid email and short password."""
    payload = {
        "email": "not-an-email",
        "password": "short",
        "full_name": "A",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "REQUEST_VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Verifies successful login returning access and refresh tokens."""
    # 1. Register
    reg_payload = {
        "email": "login.test@finpilot.com",
        "password": "ValidPassword123!",
        "full_name": "Login Tester",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # 2. Login
    login_payload = {
        "email": "login.test@finpilot.com",
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login.test@finpilot.com"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    """Verifies login failure with incorrect password returns 401."""
    reg_payload = {
        "email": "wrongpass@finpilot.com",
        "password": "CorrectPassword123!",
        "full_name": "Wrong Pass User",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "wrongpass@finpilot.com",
        "password": "IncorrectPassword999!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient) -> None:
    """Verifies that refreshing a token rotates it and revokes the old one."""
    # Register & Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh.tester@finpilot.com",
            "password": "Password123!",
            "full_name": "Refresh Tester",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh.tester@finpilot.com", "password": "Password123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # 1. First refresh (should succeed)
    ref_res1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_res1.status_code == 200
    data1 = ref_res1.json()
    assert "access_token" in data1
    assert "refresh_token" in data1
    new_refresh_token = data1["refresh_token"]
    assert new_refresh_token != refresh_token

    # 2. Second refresh with old token (must fail because it was rotated/revoked)
    ref_res2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_res2.status_code == 401


@pytest.mark.asyncio
async def test_get_me_endpoint(client: AsyncClient) -> None:
    """Verifies GET /api/v1/auth/me returns the profile of the authenticated user."""
    # Register & Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me.test@finpilot.com",
            "password": "Password123!",
            "full_name": "Me Tester",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "me.test@finpilot.com", "password": "Password123!"},
    )
    access_token = login_res.json()["access_token"]

    # 1. Authenticated request
    headers = {"Authorization": f"Bearer {access_token}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "me.test@finpilot.com"
    assert me_data["full_name"] == "Me Tester"

    # 2. Unauthenticated request (no token)
    unauth_res = await client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

    # 3. Invalid token
    bad_token_res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
    assert bad_token_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session(client: AsyncClient) -> None:
    """Verifies that logging out revokes the refresh token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout.test@finpilot.com",
            "password": "Password123!",
            "full_name": "Logout Tester",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout.test@finpilot.com", "password": "Password123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 204

    # Try to use refresh token after logout (must fail)
    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_google_login_flow(client: AsyncClient) -> None:
    """Verifies Google OAuth authentication and account linking."""
    mock_token = "mock_google_token_newuser"
    google_res = await client.post("/api/v1/auth/google", json={"id_token": mock_token})
    assert google_res.status_code == 200
    data = google_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "newuser@gmail.com"
    assert data["user"]["is_verified"] is True

    # Login again with the same Google account (should return same user)
    google_res_repeat = await client.post("/api/v1/auth/google", json={"id_token": mock_token})
    assert google_res_repeat.status_code == 200
    assert google_res_repeat.json()["user"]["id"] == data["user"]["id"]
