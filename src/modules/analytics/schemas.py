import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class CategorySpendingSummary(BaseModel):
    """Spending grouped by category with absolute amount and relative share."""

    model_config = ConfigDict(from_attributes=True)

    category_id: uuid.UUID | None = None
    category_name: str
    icon: str
    color: str
    amount_cents: int
    percentage: float


class MonthComparison(BaseModel):
    """Comparative analysis with previous month."""

    previous_income_cents: int
    previous_expense_cents: int
    income_growth_pct: float | None = None
    expense_growth_pct: float | None = None


class RecentTransactionSummary(BaseModel):
    """Summary of recent transactions for dashboard preview."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    amount_cents: int
    type: str
    category_name: str | None = None
    category_icon: str | None = None
    category_color: str | None = None
    account_name: str
    transaction_date: date


class DashboardResponse(BaseModel):
    """Aggregated financial dashboard summary."""

    total_balance_cents: int
    month_income_cents: int
    month_expense_cents: int
    month_net_cents: int
    year: int
    month: int
    comparison_previous_month: MonthComparison
    spending_by_category: list[CategorySpendingSummary]
    recent_transactions: list[RecentTransactionSummary]
