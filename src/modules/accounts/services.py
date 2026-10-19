import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import EntityNotFoundError
from src.modules.accounts.models import FinancialAccount
from src.modules.accounts.schemas import AccountCreate, AccountUpdate


class AccountService:
    """Service handling accounts and cash wallet operations with multi-tenant isolation."""

    @staticmethod
    async def list_accounts(db: AsyncSession, user_id: uuid.UUID) -> Sequence[FinancialAccount]:
        """Returns all active accounts owned by the given user."""
        stmt = (
            select(FinancialAccount)
            .where(
                FinancialAccount.user_id == user_id,
                FinancialAccount.is_active.is_(True),
            )
            .order_by(FinancialAccount.created_at.asc())
        )
        result = await db.scalars(stmt)
        return result.all()

    @staticmethod
    async def get_account(
        db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> FinancialAccount:
        """Retrieves a specific account ensuring ownership."""
        stmt = select(FinancialAccount).where(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user_id,
            FinancialAccount.is_active.is_(True),
        )
        account = await db.scalar(stmt)
        if not account:
            raise EntityNotFoundError("Account not found")
        return account

    @staticmethod
    async def create_account(
        db: AsyncSession, user_id: uuid.UUID, account_in: AccountCreate
    ) -> FinancialAccount:
        """Creates a new financial account or cash wallet for the user."""
        account = FinancialAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            name=account_in.name.strip(),
            account_type=account_in.account_type.value,
            balance_cents=account_in.initial_balance_cents,
            currency=account_in.currency.upper(),
            color=account_in.color,
            is_manual=True,
            is_active=True,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    @classmethod
    async def update_account(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        update_in: AccountUpdate,
    ) -> FinancialAccount:
        """Updates account details ensuring ownership."""
        account = await cls.get_account(db, user_id, account_id)

        if update_in.name is not None:
            account.name = update_in.name.strip()
        if update_in.account_type is not None:
            account.account_type = update_in.account_type.value
        if update_in.color is not None:
            account.color = update_in.color

        await db.commit()
        await db.refresh(account)
        return account

    @classmethod
    async def deactivate_account(
        cls, db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> None:
        """Soft-deletes an account ensuring ownership."""
        account = await cls.get_account(db, user_id, account_id)
        account.is_active = False
        await db.commit()
