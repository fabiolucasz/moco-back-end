import calendar
import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import EntityNotFoundError
from src.modules.accounts.models import FinancialAccount
from src.modules.analytics.schemas import (
    CategorySpendingSummary,
    DashboardResponse,
    MonthComparison,
    RecentTransactionSummary,
)
from src.modules.transactions.domain.enums import TransactionStatus, TransactionType
from src.modules.transactions.models import Transaction, TransactionCategory


def _get_month_date_range(year: int, month: int) -> tuple[date, date]:
    """Returns the start and end dates of a given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _get_previous_month(year: int, month: int) -> tuple[int, int]:
    """Returns the year and month of the preceding month."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


class DashboardService:
    """Service providing consolidated financial aggregates and insights."""

    @classmethod
    async def get_dashboard(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        year: int | None = None,
        month: int | None = None,
        account_id: uuid.UUID | None = None,
    ) -> DashboardResponse:
        """Computes consolidated balance, monthly totals, category shares, and metrics."""
        today = date.today()

        target_year = year or today.year
        target_month = month or today.month

        # Validate account ownership if account_id is supplied
        if account_id is not None:
            acc_check = await db.get(FinancialAccount, account_id)
            if not acc_check or acc_check.user_id != user_id or not acc_check.is_active:
                raise EntityNotFoundError("Account not found or access denied")

        # 1. Total consolidated balance
        balance_stmt = select(
            func.coalesce(func.sum(FinancialAccount.balance_cents), 0)
        ).where(
            FinancialAccount.user_id == user_id,
            FinancialAccount.is_active.is_(True),
        )
        if account_id is not None:
            balance_stmt = balance_stmt.where(FinancialAccount.id == account_id)
        total_balance_cents = int((await db.scalar(balance_stmt)) or 0)

        # 2. Date ranges
        start_date, end_date = _get_month_date_range(target_year, target_month)
        prev_year, prev_month = _get_previous_month(target_year, target_month)
        prev_start, prev_end = _get_month_date_range(prev_year, prev_month)

        # 3. Monthly Income & Expense calculation
        async def _calculate_month_totals(start: date, end: date) -> tuple[int, int]:
            stmt = (
                select(
                    Transaction.type,
                    func.coalesce(func.sum(Transaction.amount_cents), 0),
                )
                .where(
                    Transaction.user_id == user_id,
                    Transaction.status == TransactionStatus.CONFIRMED.value,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                    Transaction.type.in_(
                        [TransactionType.INCOME.value, TransactionType.EXPENSE.value]
                    ),
                )
                .group_by(Transaction.type)
            )
            if account_id is not None:
                stmt = stmt.where(
                    or_(
                        Transaction.account_id == account_id,
                        Transaction.destination_account_id == account_id,
                    )
                )

            rows = (await db.execute(stmt)).all()
            income = 0
            expense = 0
            for row_type, row_sum in rows:
                if row_type == TransactionType.INCOME.value:
                    income = int(row_sum)
                elif row_type == TransactionType.EXPENSE.value:
                    expense = int(row_sum)
            return income, expense

        month_income, month_expense = await _calculate_month_totals(
            start_date, end_date
        )
        prev_income, prev_expense = await _calculate_month_totals(prev_start, prev_end)

        # 4. Growth calculations
        income_growth_pct: float | None = None
        if prev_income > 0:
            income_growth_pct = round(
                ((month_income - prev_income) / prev_income) * 100, 1
            )

        expense_growth_pct: float | None = None
        if prev_expense > 0:
            expense_growth_pct = round(
                ((month_expense - prev_expense) / prev_expense) * 100, 1
            )

        month_net_cents = month_income - month_expense

        # 5. Spending by category for target month
        cat_stmt = (
            select(
                Transaction.category_id,
                func.coalesce(TransactionCategory.name, "Sem Categoria").label(
                    "cat_name"
                ),
                func.coalesce(TransactionCategory.icon, "help-circle").label(
                    "cat_icon"
                ),
                func.coalesce(TransactionCategory.color, "#6B7280").label("cat_color"),
                func.coalesce(func.sum(Transaction.amount_cents), 0).label(
                    "total_spent"
                ),
            )
            .outerjoin(
                TransactionCategory, Transaction.category_id == TransactionCategory.id
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.CONFIRMED.value,
                Transaction.type == TransactionType.EXPENSE.value,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(
                Transaction.category_id,
                TransactionCategory.name,
                TransactionCategory.icon,
                TransactionCategory.color,
            )
            .order_by(func.sum(Transaction.amount_cents).desc())
        )
        if account_id is not None:
            cat_stmt = cat_stmt.where(Transaction.account_id == account_id)

        cat_rows = (await db.execute(cat_stmt)).all()
        spending_by_category: list[CategorySpendingSummary] = []
        for cat_id, cat_name, cat_icon, cat_color, total_spent in cat_rows:
            spent_cents = int(total_spent)
            pct = (
                round((spent_cents / month_expense) * 100, 1)
                if month_expense > 0
                else 0.0
            )
            spending_by_category.append(
                CategorySpendingSummary(
                    category_id=cat_id,
                    category_name=cat_name,
                    icon=cat_icon,
                    color=cat_color,
                    amount_cents=spent_cents,
                    percentage=pct,
                )
            )

        # 6. Recent transactions (5 most recent)
        recent_stmt = (
            select(Transaction, FinancialAccount.name)
            .join(FinancialAccount, Transaction.account_id == FinancialAccount.id)
            .where(Transaction.user_id == user_id)
            .order_by(
                Transaction.transaction_date.desc(), Transaction.created_at.desc()
            )
            .limit(5)
        )
        if account_id is not None:
            recent_stmt = recent_stmt.where(
                or_(
                    Transaction.account_id == account_id,
                    Transaction.destination_account_id == account_id,
                )
            )

        recent_rows = (await db.execute(recent_stmt)).all()
        recent_transactions: list[RecentTransactionSummary] = []
        for tx, acc_name in recent_rows:
            tx_cat_name: str | None = tx.category.name if tx.category else None
            tx_cat_icon: str | None = tx.category.icon if tx.category else None
            tx_cat_color: str | None = tx.category.color if tx.category else None

            recent_transactions.append(
                RecentTransactionSummary(
                    id=tx.id,
                    description=tx.description,
                    amount_cents=tx.amount_cents,
                    type=tx.type,
                    category_name=tx_cat_name,
                    category_icon=tx_cat_icon,
                    category_color=tx_cat_color,
                    account_name=acc_name,
                    transaction_date=tx.transaction_date,
                )
            )

        return DashboardResponse(
            total_balance_cents=total_balance_cents,
            month_income_cents=month_income,
            month_expense_cents=month_expense,
            month_net_cents=month_net_cents,
            year=target_year,
            month=target_month,
            comparison_previous_month=MonthComparison(
                previous_income_cents=prev_income,
                previous_expense_cents=prev_expense,
                income_growth_pct=income_growth_pct,
                expense_growth_pct=expense_growth_pct,
            ),
            spending_by_category=spending_by_category,
            recent_transactions=recent_transactions,
        )
