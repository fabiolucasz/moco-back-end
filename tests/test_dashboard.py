import pytest
from httpx import AsyncClient


async def _create_user_and_login(client: AsyncClient, email: str) -> str:
    """Helper to register and login a user, returning access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Dashboard Tester"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_dashboard_consolidated_balance_and_monthly_metrics(client: AsyncClient) -> None:
    """Verifies dashboard calculates balance, monthly totals, and category breakdown."""
    token = await _create_user_and_login(client, "dash.user@finpilot.com")

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create 2 accounts: Bank (R$ 2.000) and Cash Wallet (R$ 500)
    acc1 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={
                "name": "Conta Corrente",
                "account_type": "checking",
                "initial_balance_cents": 200000,
            },
        )
    ).json()

    acc2 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={
                "name": "Carteira Dinheiro",
                "account_type": "cash_wallet",
                "initial_balance_cents": 50000,
            },
        )
    ).json()

    # 2. Get categories
    cats = (await client.get("/api/v1/categories", headers=headers)).json()
    cat_food = next(c for c in cats if c["name"] == "Alimentação")
    cat_trans = next(c for c in cats if c["name"] == "Transporte")
    cat_salary = next(c for c in cats if c["name"] == "Salário")

    # 3. Add transactions in October 2026:
    # Income: Salary R$ 5.000,00 (500000 cents)
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc1["id"],
            "category_id": cat_salary["id"],
            "amount_cents": 500000,
            "type": "income",
            "description": "Salário Outubro",
            "transaction_date": "2026-10-05",
        },
    )

    # Expense 1: Food R$ 800,00 (80000 cents)
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc1["id"],
            "category_id": cat_food["id"],
            "amount_cents": 80000,
            "type": "expense",
            "description": "Restaurante e Mercado",
            "transaction_date": "2026-10-10",
        },
    )

    # Expense 2: Transport R$ 200,00 (20000 cents) from cash wallet
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc2["id"],
            "category_id": cat_trans["id"],
            "amount_cents": 20000,
            "type": "expense",
            "description": "Combustível",
            "transaction_date": "2026-10-15",
        },
    )

    # 4. Fetch Dashboard for 2026-10
    dash_res = await client.get("/api/v1/analytics/dashboard?year=2026&month=10", headers=headers)
    assert dash_res.status_code == 200
    data = dash_res.json()

    # Total Balance:
    # Acc1: 200000 + 500000 - 80000 = 620000
    # Acc2: 50000 - 20000 = 30000
    # Consolidated: 650000 (R$ 6.500,00)
    assert data["total_balance_cents"] == 650000

    # Month Totals:
    # Income: 500000
    # Expense: 80000 + 20000 = 100000
    # Net: 400000
    assert data["month_income_cents"] == 500000
    assert data["month_expense_cents"] == 100000
    assert data["month_net_cents"] == 400000

    # Category Spending:
    # Total expense: 100000. Food: 80000 (80%), Transport: 20000 (20%)
    categories_spent = data["spending_by_category"]
    assert len(categories_spent) == 2
    food_summary = next(c for c in categories_spent if c["category_name"] == "Alimentação")
    assert food_summary["amount_cents"] == 80000
    assert food_summary["percentage"] == 80.0

    trans_summary = next(c for c in categories_spent if c["category_name"] == "Transporte")
    assert trans_summary["amount_cents"] == 20000
    assert trans_summary["percentage"] == 20.0

    # Recent Transactions: 3 items returned
    assert len(data["recent_transactions"]) == 3
    assert data["recent_transactions"][0]["description"] == "Combustível"


@pytest.mark.asyncio
async def test_dashboard_multi_tenant_isolation(client: AsyncClient) -> None:
    """Ensures dashboard metrics only include the authenticated user's data."""
    token_alice = await _create_user_and_login(client, "alice.dash@finpilot.com")
    token_bob = await _create_user_and_login(client, "bob.dash@finpilot.com")

    # Alice has 1 million cents
    await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_alice}"},
        json={
            "name": "Alice Rich Account",
            "account_type": "savings",
            "initial_balance_cents": 1000000,
        },
    )

    # Bob has 0 cents
    await client.post(
        "/api/v1/accounts",
        headers={"Authorization": f"Bearer {token_bob}"},
        json={
            "name": "Bob Empty Account",
            "account_type": "checking",
            "initial_balance_cents": 0,
        },
    )

    # Bob checks dashboard -> total balance must be 0, not 1 million!
    bob_dash = await client.get(
        "/api/v1/analytics/dashboard",
        headers={"Authorization": f"Bearer {token_bob}"},
    )

    assert bob_dash.status_code == 200
    assert bob_dash.json()["total_balance_cents"] == 0
    assert bob_dash.json()["month_income_cents"] == 0
    assert bob_dash.json()["month_expense_cents"] == 0
