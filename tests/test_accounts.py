import pytest
from httpx import AsyncClient


async def _create_user_and_login(client: AsyncClient, email: str) -> str:
    """Helper to register and login a user, returning access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Test User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_create_cash_wallet_and_checking_account(client: AsyncClient) -> None:
    """Verifies creation of physical cash wallet and checking accounts with initial balance."""
    token = await _create_user_and_login(client, "wallet.user@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Physical Cash Wallet
    wallet_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": "Carteira de Bolso",
            "account_type": "cash_wallet",
            "initial_balance_cents": 15000,  # R$ 150,00
            "color": "#10B981",
        },
    )
    assert wallet_res.status_code == 201
    wallet_data = wallet_res.json()
    assert wallet_data["name"] == "Carteira de Bolso"
    assert wallet_data["account_type"] == "cash_wallet"
    assert wallet_data["balance_cents"] == 15000
    assert wallet_data["is_manual"] is True

    # 2. Bank Account
    bank_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": "Nubank",
            "account_type": "checking",
            "initial_balance_cents": 250000,  # R$ 2.500,00
            "color": "#820AD1",
        },
    )
    assert bank_res.status_code == 201
    bank_data = bank_res.json()
    assert bank_data["name"] == "Nubank"
    assert bank_data["balance_cents"] == 250000


@pytest.mark.asyncio
async def test_list_accounts_multi_tenant_isolation(client: AsyncClient) -> None:
    """Ensures users only see their own accounts."""
    token_a = await _create_user_and_login(client, "user_a@finpilot.com")
    token_b = await _create_user_and_login(client, "user_b@finpilot.com")

    # User A creates 2 accounts
    await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Conta A1", "account_type": "checking", "initial_balance_cents": 1000},
    )
    await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Conta A2", "account_type": "cash_wallet", "initial_balance_cents": 2000},
    )

    # User B creates 1 account
    await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"name": "Conta B1", "account_type": "checking", "initial_balance_cents": 5000},
    )

    # Check User A accounts
    list_a = await client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_a}"})
    assert list_a.status_code == 200
    accounts_a = list_a.json()
    assert len(accounts_a) == 2
    assert all(a["name"].startswith("Conta A") for a in accounts_a)

    # Check User B accounts
    list_b = await client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token_b}"})
    assert list_b.status_code == 200
    accounts_b = list_b.json()
    assert len(accounts_b) == 1
    assert accounts_b[0]["name"] == "Conta B1"


@pytest.mark.asyncio
async def test_get_other_user_account_returns_404(client: AsyncClient) -> None:
    """Security test: Attempting to access another user's account must return 404 Not Found."""
    token_a = await _create_user_and_login(client, "alice@finpilot.com")
    token_b = await _create_user_and_login(client, "bob@finpilot.com")

    # Alice creates an account
    res = await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Alice Secret Account",
            "account_type": "savings",
            "initial_balance_cents": 100000,
        },
    )
    alice_acc_id = res.json()["id"]

    # Bob tries to access Alice's account ID directly
    unauth_access = await client.get(
        f"/api/v1/accounts/{alice_acc_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert unauth_access.status_code == 404
    assert unauth_access.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_and_deactivate_account(client: AsyncClient) -> None:
    """Verifies updating name and deactivating (soft-deleting) an account."""
    token = await _create_user_and_login(client, "account_mgmt@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Old Account Name", "account_type": "checking", "initial_balance_cents": 0},
    )
    acc_id = create_res.json()["id"]

    # Update
    update_res = await client.put(
        f"/api/v1/accounts/{acc_id}",
        headers=headers,
        json={"name": "New Account Name", "color": "#00FF00"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "New Account Name"
    assert update_res.json()["color"] == "#00FF00"

    # Deactivate
    del_res = await client.delete(f"/api/v1/accounts/{acc_id}", headers=headers)
    assert del_res.status_code == 204

    # Now get should return 404
    get_res = await client.get(f"/api/v1/accounts/{acc_id}", headers=headers)
    assert get_res.status_code == 404
