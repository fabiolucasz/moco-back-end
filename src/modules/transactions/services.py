import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleValidationError, EntityNotFoundError
from src.modules.accounts.models import FinancialAccount
from src.modules.accounts.services import AccountService
from src.modules.transactions.domain.enums import (
    CategoryType,
    TransactionOrigin,
    TransactionStatus,
    TransactionType,
)
from src.modules.transactions.models import Transaction, TransactionCategory
from src.modules.transactions.schemas import (
    CategoryCreate,
    CategoryUpdate,
    TransactionCreate,
    TransactionUpdate,
)

# Standard Brazilian default categories seed
SYSTEM_CATEGORIES = [
    # Expenses
    {
        "name": "Alimentação",
        "icon": "utensils",
        "color": "#EF4444",
        "type": CategoryType.EXPENSE.value,
    },
    {"name": "Moradia", "icon": "home", "color": "#F59E0B", "type": "expense"},
    {"name": "Transporte", "icon": "car", "color": "#3B82F6", "type": "expense"},
    {"name": "Saúde", "icon": "heart", "color": "#10B981", "type": "expense"},
    {"name": "Educação", "icon": "book", "color": "#8B5CF6", "type": "expense"},
    {"name": "Lazer", "icon": "film", "color": "#EC4899", "type": "expense"},
    {"name": "Assinaturas", "icon": "refresh-cw", "color": "#6366F1", "type": "expense"},
    {"name": "Compras", "icon": "shopping-bag", "color": "#14B8A6", "type": "expense"},
    {"name": "Impostos", "icon": "file-text", "color": "#6B7280", "type": "expense"},
    {"name": "Investimentos", "icon": "trending-up", "color": "#059669", "type": "expense"},
    # Income
    {"name": "Salário", "icon": "briefcase", "color": "#10B981", "type": "income"},
    {"name": "Renda Extra", "icon": "plus-circle", "color": "#34D399", "type": "income"},
    {"name": "Rendimentos", "icon": "dollar-sign", "color": "#059669", "type": "income"},
    {"name": "Outras Receitas", "icon": "arrow-down-circle", "color": "#6EE7B7", "type": "income"},
    # Transfer
    {"name": "Transferência", "icon": "repeat", "color": "#64748B", "type": "transfer"},
]


class CategoryService:
    """Service handling transaction categories."""

    @staticmethod
    async def seed_system_categories(db: AsyncSession) -> None:
        """Seeds default categories if not already present."""
        stmt = select(TransactionCategory).where(TransactionCategory.is_system_default.is_(True))
        existing = await db.scalars(stmt)
        if existing.first() is not None:
            return

        for item in SYSTEM_CATEGORIES:
            cat = TransactionCategory(
                id=uuid.uuid4(),
                user_id=None,
                name=item["name"],
                icon=item["icon"],
                color=item["color"],
                type=item["type"],
                is_system_default=True,
            )
            db.add(cat)
        await db.commit()

    @staticmethod
    async def list_categories(
        db: AsyncSession, user_id: uuid.UUID, category_type: CategoryType | None = None
    ) -> Sequence[TransactionCategory]:
        """Returns system categories and custom categories owned by the user."""
        conditions = [
            or_(
                TransactionCategory.is_system_default.is_(True),
                TransactionCategory.user_id == user_id,
            )
        ]
        if category_type is not None:
            conditions.append(TransactionCategory.type == category_type.value)

        stmt = (
            select(TransactionCategory)
            .where(*conditions)
            .order_by(TransactionCategory.is_system_default.desc(), TransactionCategory.name.asc())
        )
        result = await db.scalars(stmt)
        return result.all()

    @staticmethod
    async def create_custom_category(
        db: AsyncSession, user_id: uuid.UUID, cat_in: CategoryCreate
    ) -> TransactionCategory:
        """Creates a personal category for the user."""
        category = TransactionCategory(
            id=uuid.uuid4(),
            user_id=user_id,
            name=cat_in.name.strip(),
            icon=cat_in.icon,
            color=cat_in.color,
            type=cat_in.type.value,
            parent_id=cat_in.parent_id,
            is_system_default=False,
        )
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category

    @staticmethod
    async def update_custom_category(
        db: AsyncSession,
        user_id: uuid.UUID,
        category_id: uuid.UUID,
        cat_update: CategoryUpdate,
    ) -> TransactionCategory:
        """Updates a custom category owned by the user."""
        category = await db.get(TransactionCategory, category_id)
        if not category or category.user_id != user_id:
            raise EntityNotFoundError("Category not found or access denied")
        if category.is_system_default:
            raise BusinessRuleValidationError("Cannot modify system default categories")

        if cat_update.name is not None:
            category.name = cat_update.name.strip()
        if cat_update.icon is not None:
            category.icon = cat_update.icon
        if cat_update.color is not None:
            category.color = cat_update.color
        if cat_update.type is not None:
            category.type = cat_update.type.value

        await db.commit()
        await db.refresh(category)
        return category

    @staticmethod
    async def delete_custom_category(
        db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        """Deletes a custom category and disassociates related transactions."""
        category = await db.get(TransactionCategory, category_id)
        if not category or category.user_id != user_id:
            raise EntityNotFoundError("Category not found or access denied")
        if category.is_system_default:
            raise BusinessRuleValidationError("Cannot delete system default categories")

        # Disassociate transactions using this category
        stmt = (
            update(Transaction)
            .where(Transaction.category_id == category_id, Transaction.user_id == user_id)
            .values(category_id=None)
        )
        await db.execute(stmt)

        await db.delete(category)
        await db.commit()


class TransactionService:
    """Service handling transactions with atomic balance updates and multi-tenant isolation."""

    @staticmethod
    def _apply_balance_effect(
        account: FinancialAccount,
        dest_account: FinancialAccount | None,
        tx_type: str,
        amount_cents: int,
        status: str,
        revert: bool = False,
    ) -> None:
        """Modifies accounts balance according to transaction type and status."""
        if status != TransactionStatus.CONFIRMED.value:
            return

        factor = -1 if revert else 1

        if tx_type == TransactionType.INCOME.value:
            account.balance_cents += factor * amount_cents
        elif tx_type == TransactionType.EXPENSE.value:
            account.balance_cents -= factor * amount_cents
        elif tx_type == TransactionType.TRANSFER.value:
            account.balance_cents -= factor * amount_cents
            if dest_account:
                dest_account.balance_cents += factor * amount_cents

    @classmethod
    async def create_transaction(
        cls, db: AsyncSession, user_id: uuid.UUID, tx_in: TransactionCreate
    ) -> Transaction:
        """Creates a transaction and atomically updates account balances."""
        # Validate account ownership or assign user default account
        if tx_in.account_id is None:
            account = await AccountService.get_or_create_default_account(db, user_id)
            source_account_id = account.id
        else:
            account = await db.get(FinancialAccount, tx_in.account_id)
            if not account or account.user_id != user_id or not account.is_active:
                raise EntityNotFoundError("Source account not found or access denied")
            source_account_id = account.id

        dest_account: FinancialAccount | None = None
        if tx_in.type == TransactionType.TRANSFER:
            if not tx_in.destination_account_id:
                raise BusinessRuleValidationError("Transfer requires a destination account")
            dest_account = await db.get(FinancialAccount, tx_in.destination_account_id)
            if not dest_account or dest_account.user_id != user_id or not dest_account.is_active:
                raise EntityNotFoundError("Destination account not found or access denied")

        # Validate category if provided
        if tx_in.category_id:
            category = await db.get(TransactionCategory, tx_in.category_id)
            if not category or (category.user_id is not None and category.user_id != user_id):
                raise EntityNotFoundError("Category not found or access denied")

        transaction = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            account_id=source_account_id,
            destination_account_id=tx_in.destination_account_id,
            category_id=tx_in.category_id,
            amount_cents=tx_in.amount_cents,
            type=tx_in.type.value,
            description=tx_in.description.strip(),
            transaction_date=tx_in.transaction_date,
            settlement_date=tx_in.settlement_date,
            status=tx_in.status.value,
            origin=TransactionOrigin.MANUAL.value,
            notes=tx_in.notes,
        )

        # Apply balance impact
        cls._apply_balance_effect(
            account=account,
            dest_account=dest_account,
            tx_type=transaction.type,
            amount_cents=transaction.amount_cents,
            status=transaction.status,
            revert=False,
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return transaction

    @classmethod
    async def get_transaction(
        cls, db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Transaction:
        """Retrieves a single transaction ensuring user ownership."""
        stmt = select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        )
        tx = await db.scalar(stmt)
        if not tx:
            raise EntityNotFoundError("Transaction not found")
        return tx

    @classmethod
    async def list_transactions(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        tx_type: TransactionType | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Transaction]:
        """Lists transactions with filters and pagination."""
        stmt = select(Transaction).where(Transaction.user_id == user_id)

        if account_id is not None:
            stmt = stmt.where(
                or_(
                    Transaction.account_id == account_id,
                    Transaction.destination_account_id == account_id,
                )
            )
        if category_id is not None:
            stmt = stmt.where(Transaction.category_id == category_id)
        if tx_type is not None:
            stmt = stmt.where(Transaction.type == tx_type.value)
        if start_date is not None:
            stmt = stmt.where(Transaction.transaction_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(Transaction.transaction_date <= end_date)

        stmt = stmt.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await db.scalars(stmt)
        return result.all()

    @classmethod
    async def delete_transaction(
        cls, db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> None:
        """Deletes a transaction and reverses its balance impact."""
        tx = await cls.get_transaction(db, user_id, transaction_id)

        account = await db.get(FinancialAccount, tx.account_id)
        dest_account = (
            await db.get(FinancialAccount, tx.destination_account_id)
            if tx.destination_account_id
            else None
        )

        if account:
            cls._apply_balance_effect(
                account=account,
                dest_account=dest_account,
                tx_type=tx.type,
                amount_cents=tx.amount_cents,
                status=tx.status,
                revert=True,
            )

        await db.delete(tx)
        await db.commit()

    @classmethod
    async def update_transaction(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        update_in: TransactionUpdate,
    ) -> Transaction:
        """Updates a transaction, accurately reconciling account balances."""
        tx = await cls.get_transaction(db, user_id, transaction_id)

        account = await db.get(FinancialAccount, tx.account_id)
        dest_account = (
            await db.get(FinancialAccount, tx.destination_account_id)
            if tx.destination_account_id
            else None
        )

        # 1. Revert existing balance effect
        if account:
            cls._apply_balance_effect(
                account=account,
                dest_account=dest_account,
                tx_type=tx.type,
                amount_cents=tx.amount_cents,
                status=tx.status,
                revert=True,
            )

        # 2. Update fields
        target_account = account
        if update_in.account_id is not None and update_in.account_id != tx.account_id:
            new_acc = await db.get(FinancialAccount, update_in.account_id)
            if not new_acc or new_acc.user_id != user_id or not new_acc.is_active:
                raise EntityNotFoundError("New account not found or access denied")
            tx.account_id = update_in.account_id
            target_account = new_acc

        if update_in.category_id is not None:
            category = await db.get(TransactionCategory, update_in.category_id)
            if not category or (category.user_id is not None and category.user_id != user_id):
                raise EntityNotFoundError("Category not found or access denied")
            tx.category_id = update_in.category_id
        if update_in.amount_cents is not None:
            tx.amount_cents = update_in.amount_cents
        if update_in.type is not None:
            tx.type = update_in.type.value
        if update_in.description is not None:
            tx.description = update_in.description.strip()
        if update_in.transaction_date is not None:
            tx.transaction_date = update_in.transaction_date
        if update_in.status is not None:
            tx.status = update_in.status.value
        if update_in.notes is not None:
            tx.notes = update_in.notes

        # 3. Apply new balance effect
        if target_account:
            cls._apply_balance_effect(
                account=target_account,
                dest_account=dest_account,
                tx_type=tx.type,
                amount_cents=tx.amount_cents,
                status=tx.status,
                revert=False,
            )

        await db.commit()
        await db.refresh(tx)
        return tx
