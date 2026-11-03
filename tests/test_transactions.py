import pytest
from httpx import AsyncClient


async def _create_user_and_login(client: AsyncClient, email: str) -> str:
    """Helper to register and login a user, returning access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Finance Tester"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_categories_seed_and_custom_creation(client: AsyncClient) -> None:
    """Verifies that system default categories are seeded and custom categories can be created."""
    token = await _create_user_and_login(client, "cat.user@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List default categories
    list_res = await client.get("/api/v1/categories", headers=headers)
    assert list_res.status_code == 200
    categories = list_res.json()
    assert len(categories) >= 15
    cat_names = [c["name"] for c in categories]
    assert "Alimentação" in cat_names
    assert "Salário" in cat_names
    assert "Transferência" in cat_names

    # 2. Create custom category
    custom_res = await client.post(
        "/api/v1/categories",
        headers=headers,
        json={
            "name": "Consultoria TI",
            "icon": "laptop",
            "color": "#6366F1",
            "type": "income",
        },
    )
    assert custom_res.status_code == 201
    custom_data = custom_res.json()
    assert custom_data["name"] == "Consultoria TI"
    assert custom_data["is_system_default"] is False


@pytest.mark.asyncio
async def test_income_and_expense_transactions_update_balance(client: AsyncClient) -> None:
    """Verifies that income increases and expense decreases balance in cents."""
    token = await _create_user_and_login(client, "tx.calc@finpilot.com")

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create checking account with initial R$ 1.000,00 (100000 cents)
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": "Banco Principal",
            "account_type": "checking",
            "initial_balance_cents": 100000,
        },
    )
    acc_id = acc_res.json()["id"]

    # 2. Register Expense of R$ 150,50 (15050 cents)
    exp_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "amount_cents": 15050,
            "type": "expense",
            "description": "Supermercado Semanal",
            "transaction_date": "2026-10-19",
        },
    )
    assert exp_res.status_code == 201

    # Verify balance decreased: 100000 - 15050 = 84950
    acc_after_exp = await client.get(f"/api/v1/accounts/{acc_id}", headers=headers)
    assert acc_after_exp.json()["balance_cents"] == 84950

    # 3. Register Income of R$ 500,00 (50000 cents)
    inc_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "amount_cents": 50000,
            "type": "income",
            "description": "Venda de Item Usado",
            "transaction_date": "2026-10-19",
        },
    )
    assert inc_res.status_code == 201

    # Verify balance increased: 84950 + 50000 = 134950
    acc_after_inc = await client.get(f"/api/v1/accounts/{acc_id}", headers=headers)
    assert acc_after_inc.json()["balance_cents"] == 134950


@pytest.mark.asyncio
async def test_transfer_between_accounts(client: AsyncClient) -> None:
    """Verifies that transfer atomically moves funds between source and destination accounts."""
    token = await _create_user_and_login(client, "transfer.user@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Account 1: Bank (Initial 50000 cents / R$ 500,00)
    acc1 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={
                "name": "Conta Corrente",
                "account_type": "checking",
                "initial_balance_cents": 50000,
            },
        )
    ).json()

    # Account 2: Physical Cash Wallet (Initial 0 cents)
    acc2 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={
                "name": "Carteira Dinheiro",
                "account_type": "cash_wallet",
                "initial_balance_cents": 0,
            },
        )
    ).json()

    # Saque no caixa eletrônico: Transfer R$ 200,00 (20000 cents) from Bank to Cash Wallet
    tx_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc1["id"],
            "destination_account_id": acc2["id"],
            "amount_cents": 20000,
            "type": "transfer",
            "description": "Saque Banco24Horas",
            "transaction_date": "2026-10-19",
        },
    )
    assert tx_res.status_code == 201

    # Check Balances: Acc1 should have 30000, Acc2 should have 20000
    acc1_updated = await client.get(f"/api/v1/accounts/{acc1['id']}", headers=headers)
    acc2_updated = await client.get(f"/api/v1/accounts/{acc2['id']}", headers=headers)
    assert acc1_updated.json()["balance_cents"] == 30000
    assert acc2_updated.json()["balance_cents"] == 20000


@pytest.mark.asyncio
async def test_delete_transaction_reverses_balance(client: AsyncClient) -> None:
    """Verifies that deleting an expense restores the deducted funds."""
    token = await _create_user_and_login(client, "delete.tx@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    acc = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={
                "name": "Conta Teste Delete",
                "account_type": "checking",
                "initial_balance_cents": 10000,
            },
        )
    ).json()

    # Create Expense of R$ 30,00 (3000 cents) -> Balance becomes 7000
    tx = (
        await client.post(
            "/api/v1/transactions",
            headers=headers,
            json={
                "account_id": acc["id"],
                "amount_cents": 3000,
                "type": "expense",
                "description": "Café da manhã",
                "transaction_date": "2026-10-19",
            },
        )
    ).json()

    acc_check1 = await client.get(f"/api/v1/accounts/{acc['id']}", headers=headers)
    assert acc_check1.json()["balance_cents"] == 7000

    # Delete transaction
    del_res = await client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers)
    assert del_res.status_code == 204

    # Balance restored back to 10000
    acc_check2 = await client.get(f"/api/v1/accounts/{acc['id']}", headers=headers)
    assert acc_check2.json()["balance_cents"] == 10000


@pytest.mark.asyncio
async def test_multi_tenant_transaction_security(client: AsyncClient) -> None:
    """Ensures a user cannot post transactions to or access transactions of another user."""
    token_alice = await _create_user_and_login(client, "alice.finance@finpilot.com")
    token_eve = await _create_user_and_login(client, "eve.finance@finpilot.com")

    # Alice creates an account
    alice_acc = (
        await client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token_alice}"},
            json={"name": "Alice Bank", "account_type": "checking", "initial_balance_cents": 50000},
        )
    ).json()

    # Eve tries to post a transaction into Alice's account -> 404 Not Found
    unauth_post = await client.post(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token_eve}"},
        json={
            "account_id": alice_acc["id"],
            "amount_cents": 5000,
            "type": "expense",
            "description": "Eve unauthorized spend",
            "transaction_date": "2026-10-19",
        },
    )
    assert unauth_post.status_code == 404

    # Alice creates a valid transaction
    alice_tx = (
        await client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {token_alice}"},
            json={
                "account_id": alice_acc["id"],
                "amount_cents": 1000,
                "type": "expense",
                "description": "Alice coffee",
                "transaction_date": "2026-10-19",
            },
        )
    ).json()

    # Eve tries to read Alice's transaction directly -> 404 Not Found
    unauth_get = await client.get(
        f"/api/v1/transactions/{alice_tx['id']}",
        headers={"Authorization": f"Bearer {token_eve}"},
    )
    assert unauth_get.status_code == 404

    # Eve lists transactions -> should be empty
    eve_list = await client.get(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token_eve}"},
    )
    assert eve_list.status_code == 200
    assert len(eve_list.json()) == 0


@pytest.mark.asyncio
async def test_category_custom_update_and_delete(client: AsyncClient) -> None:
    """Verifies that custom categories can be updated and deleted, but system categories cannot."""
    token = await _create_user_and_login(client, "cat.custom.user@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create custom category
    create_res = await client.post(
        "/api/v1/categories",
        headers=headers,
        json={"name": "Academia", "icon": "dumbbell", "color": "#10B981", "type": "expense"},
    )
    assert create_res.status_code == 201
    cat_id = create_res.json()["id"]

    # 2. Update custom category
    update_res = await client.put(
        f"/api/v1/categories/{cat_id}",
        headers=headers,
        json={"name": "Crossfit & Natação", "color": "#059669"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Crossfit & Natação"
    assert update_res.json()["color"] == "#059669"

    # 3. Create a transaction using this category
    tx_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "amount_cents": 12000,
            "type": "expense",
            "description": "Mensalidade Crossfit",
            "category_id": cat_id,
        },
    )
    assert tx_res.status_code == 201
    tx_id = tx_res.json()["id"]

    # 4. Delete custom category
    del_res = await client.delete(f"/api/v1/categories/{cat_id}", headers=headers)
    assert del_res.status_code == 204

    # 5. Verify transaction still exists with category_id set to None
    tx_check = await client.get(f"/api/v1/transactions/{tx_id}", headers=headers)
    assert tx_check.status_code == 200
    assert tx_check.json()["category_id"] is None


@pytest.mark.asyncio
async def test_transaction_update_and_auto_account(client: AsyncClient) -> None:
    """Verifies that transactions can be created without explicit account_id and updated."""
    token = await _create_user_and_login(client, "auto.acc.user@finpilot.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create transaction without specifying account_id (system auto-creates default account)
    tx_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "amount_cents": 5000,
            "type": "expense",
            "description": "Lanche da tarde",
            "transaction_date": "2026-10-20",
        },
    )
    assert tx_res.status_code == 201
    tx_data = tx_res.json()
    assert tx_data["account_id"] is not None
    assert tx_data["account_name"] == "Carteira Principal"

    # 2. Update transaction amount and description
    tx_id = tx_data["id"]
    put_res = await client.put(
        f"/api/v1/transactions/{tx_id}",
        headers=headers,
        json={"amount_cents": 7500, "description": "Lanche da tarde reforçado"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["amount_cents"] == 7500
    assert put_res.json()["description"] == "Lanche da tarde reforçado"
