import uuid
from collections.abc import Sequence
from datetime import date, timedelta

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
    {
        "name": "Assinaturas",
        "icon": "refresh-cw",
        "color": "#6366F1",
        "type": "expense",
    },
    {"name": "Compras", "icon": "shopping-bag", "color": "#14B8A6", "type": "expense"},
    {"name": "Impostos", "icon": "file-text", "color": "#6B7280", "type": "expense"},
    {
        "name": "Investimentos",
        "icon": "trending-up",
        "color": "#059669",
        "type": "expense",
    },
    # Income
    {"name": "Salário", "icon": "briefcase", "color": "#10B981", "type": "income"},
    {
        "name": "Renda Extra",
        "icon": "plus-circle",
        "color": "#34D399",
        "type": "income",
    },
    {
        "name": "Rendimentos",
        "icon": "dollar-sign",
        "color": "#059669",
        "type": "income",
    },
    {
        "name": "Outras Receitas",
        "icon": "arrow-down-circle",
        "color": "#6EE7B7",
        "type": "income",
    },
    # Transfer
    {"name": "Transferência", "icon": "repeat", "color": "#64748B", "type": "transfer"},
]


class CategoryService:
    """Service handling transaction categories."""

    @staticmethod
    async def seed_system_categories(db: AsyncSession) -> None:
        """Seeds default categories if not already present."""
        stmt = select(TransactionCategory).where(
            TransactionCategory.is_system_default.is_(True)
        )
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
            .order_by(
                TransactionCategory.is_system_default.desc(),
                TransactionCategory.name.asc(),
            )
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
            .where(
                Transaction.category_id == category_id, Transaction.user_id == user_id
            )
            .values(category_id=None)
        )
        await db.execute(stmt)

        await db.delete(category)
        await db.commit()


class TransactionService:
    """Service handling transactions with atomic balance updates and multi-tenant isolation."""

    @staticmethod
    def _calculate_next_date(
        current_date: date, recurrence_type: str, interval: int
    ) -> date:
        """Calculates the next occurrence date based on recurrence type."""
        if recurrence_type == "daily":
            return current_date + timedelta(days=interval)
        elif recurrence_type == "weekly":
            return current_date + timedelta(weeks=interval)
        elif recurrence_type == "monthly":
            # Add months (simplified approach)
            new_month = current_date.month + interval
            year = current_date.year + (new_month - 1) // 12
            month = (new_month - 1) % 12 + 1
            # Handle day overflow (e.g., Jan 31 -> Feb 28/29)
            day = min(
                current_date.day,
                (
                    31
                    if month in [1, 3, 5, 7, 8, 10, 12]
                    else 30 if month != 2 else 29 if year % 4 == 0 else 28
                ),
            )
            return date(year, month, day)
        elif recurrence_type == "yearly":
            return date(
                current_date.year + interval, current_date.month, current_date.day
            )
        return current_date

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
        """Creates a transaction and atomically updates account balances.

        Handles recurring transactions.
        """
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
                raise BusinessRuleValidationError(
                    "Transfer requires a destination account"
                )
            dest_account = await db.get(FinancialAccount, tx_in.destination_account_id)
            if (
                not dest_account
                or dest_account.user_id != user_id
                or not dest_account.is_active
            ):
                raise EntityNotFoundError(
                    "Destination account not found or access denied"
                )

        # Validate category if provided
        if tx_in.category_id:
            category = await db.get(TransactionCategory, tx_in.category_id)
            if not category or (
                category.user_id is not None and category.user_id != user_id
            ):
                raise EntityNotFoundError("Category not found or access denied")

        # Create parent transaction
        parent_transaction = Transaction(
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
            recurrence_type=tx_in.recurrence_type,
            recurrence_interval=tx_in.recurrence_interval,
            recurrence_count=tx_in.recurrence_count,
            recurrence_end_date=tx_in.recurrence_end_date,
            installment_number=tx_in.installment_number,
            total_installments=tx_in.total_installments,
        )

        # Apply balance impact for parent
        cls._apply_balance_effect(
            account=account,
            dest_account=dest_account,
            tx_type=parent_transaction.type,
            amount_cents=parent_transaction.amount_cents,
            status=parent_transaction.status,
            revert=False,
        )

        db.add(parent_transaction)
        await db.flush()

        # Create recurring child transactions if recurrence is specified
        if tx_in.recurrence_type and tx_in.recurrence_type != "installments":
            current_date = tx_in.transaction_date
            interval = tx_in.recurrence_interval or 1
            count = tx_in.recurrence_count or 1
            end_date = tx_in.recurrence_end_date

            occurrences_created = 0
            while occurrences_created < count:
                if end_date and current_date >= end_date:
                    break

                current_date = cls._calculate_next_date(
                    current_date, tx_in.recurrence_type, interval
                )
                occurrences_created += 1

                if occurrences_created >= count:
                    break

                child_transaction = Transaction(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    account_id=source_account_id,
                    destination_account_id=tx_in.destination_account_id,
                    category_id=tx_in.category_id,
                    amount_cents=tx_in.amount_cents,
                    type=tx_in.type.value,
                    description=tx_in.description.strip(),
                    transaction_date=current_date,
                    settlement_date=tx_in.settlement_date,
                    status=tx_in.status.value,
                    origin=TransactionOrigin.MANUAL.value,
                    notes=tx_in.notes,
                    recurrence_type=tx_in.recurrence_type,
                    recurrence_interval=tx_in.recurrence_interval,
                    recurrence_count=tx_in.recurrence_count,
                    recurrence_end_date=tx_in.recurrence_end_date,
                    parent_transaction_id=parent_transaction.id,
                )

                # Apply balance impact for child
                cls._apply_balance_effect(
                    account=account,
                    dest_account=dest_account,
                    tx_type=child_transaction.type,
                    amount_cents=child_transaction.amount_cents,
                    status=child_transaction.status,
                    revert=False,
                )

                db.add(child_transaction)

        # Create installments if specified
        elif tx_in.recurrence_type == "installments" and tx_in.total_installments:
            installment_amount = tx_in.amount_cents // tx_in.total_installments
            remainder = tx_in.amount_cents % tx_in.total_installments

            for i in range(1, tx_in.total_installments + 1):
                installment_date = cls._calculate_next_date(
                    tx_in.transaction_date, "monthly", i - 1
                )
                installment_amount_adjusted = installment_amount + (
                    remainder if i == tx_in.total_installments else 0
                )

                if i == 1:
                    # First installment is the parent transaction
                    parent_transaction.amount_cents = installment_amount_adjusted
                    parent_transaction.installment_number = i
                    parent_transaction.total_installments = tx_in.total_installments
                else:
                    child_transaction = Transaction(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        account_id=source_account_id,
                        destination_account_id=tx_in.destination_account_id,
                        category_id=tx_in.category_id,
                        amount_cents=installment_amount_adjusted,
                        type=tx_in.type.value,
                        description=tx_in.description.strip(),
                        transaction_date=installment_date,
                        settlement_date=tx_in.settlement_date,
                        status=tx_in.status.value,
                        origin=TransactionOrigin.MANUAL.value,
                        notes=tx_in.notes,
                        recurrence_type="installments",
                        installment_number=i,
                        total_installments=tx_in.total_installments,
                        parent_transaction_id=parent_transaction.id,
                    )

                    # Apply balance impact for installment
                    cls._apply_balance_effect(
                        account=account,
                        dest_account=dest_account,
                        tx_type=child_transaction.type,
                        amount_cents=child_transaction.amount_cents,
                        status=child_transaction.status,
                        revert=False,
                    )

                    db.add(child_transaction)

        await db.commit()
        await db.refresh(parent_transaction)
        return parent_transaction

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

        stmt = stmt.order_by(
            Transaction.transaction_date.desc(), Transaction.created_at.desc()
        )
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
        """Updates a transaction, accurately reconciling account balances.

        Handles edit scope for recurring transactions.
        """
        tx = await cls.get_transaction(db, user_id, transaction_id)

        # Handle edit scope for recurring transactions
        edit_scope = update_in.edit_scope or "single"
        transactions_to_update = [tx]

        if edit_scope == "future" and tx.parent_transaction_id:
            # Get all child transactions with date >= current transaction date
            stmt = (
                select(Transaction)
                .where(
                    Transaction.parent_transaction_id == tx.parent_transaction_id,
                    Transaction.transaction_date >= tx.transaction_date,
                    Transaction.user_id == user_id,
                )
                .order_by(Transaction.transaction_date)
            )
            transactions_to_update = await db.scalars(stmt)
            transactions_to_update = list(transactions_to_update)
        elif edit_scope == "all" and tx.parent_transaction_id:
            # Get all transactions in the recurrence group
            stmt = (
                select(Transaction)
                .where(
                    Transaction.parent_transaction_id == tx.parent_transaction_id,
                    Transaction.user_id == user_id,
                )
                .order_by(Transaction.transaction_date)
            )
            transactions_to_update = await db.scalars(stmt)
            transactions_to_update = list(transactions_to_update)
        elif (
            edit_scope == "future" or edit_scope == "all"
        ) and not tx.parent_transaction_id:
            # This is a parent transaction, get all children
            stmt = (
                select(Transaction)
                .where(
                    Transaction.parent_transaction_id == tx.id,
                    Transaction.user_id == user_id,
                )
                .order_by(Transaction.transaction_date)
            )
            child_transactions = await db.scalars(stmt)
            if edit_scope == "future":
                transactions_to_update = [tx] + [
                    t
                    for t in child_transactions
                    if t.transaction_date >= tx.transaction_date
                ]
            else:
                transactions_to_update = [tx] + list(child_transactions)

        # Update each transaction in scope
        for current_tx in transactions_to_update:
            current_account = await db.get(FinancialAccount, current_tx.account_id)
            current_dest_account = (
                await db.get(FinancialAccount, current_tx.destination_account_id)
                if current_tx.destination_account_id
                else None
            )

            # 1. Revert existing balance effect
            if current_account:
                cls._apply_balance_effect(
                    account=current_account,
                    dest_account=current_dest_account,
                    tx_type=current_tx.type,
                    amount_cents=current_tx.amount_cents,
                    status=current_tx.status,
                    revert=True,
                )

            # 2. Update fields
            target_account = current_account
            if (
                update_in.account_id is not None
                and update_in.account_id != current_tx.account_id
            ):
                new_acc = await db.get(FinancialAccount, update_in.account_id)
                if not new_acc or new_acc.user_id != user_id or not new_acc.is_active:
                    raise EntityNotFoundError("New account not found or access denied")
                current_tx.account_id = update_in.account_id
                target_account = new_acc

            if update_in.category_id is not None:
                category = await db.get(TransactionCategory, update_in.category_id)
                if not category or (
                    category.user_id is not None and category.user_id != user_id
                ):
                    raise EntityNotFoundError("Category not found or access denied")
                current_tx.category_id = update_in.category_id
            if update_in.amount_cents is not None:
                current_tx.amount_cents = update_in.amount_cents
            if update_in.type is not None:
                current_tx.type = update_in.type.value
            if update_in.description is not None:
                current_tx.description = update_in.description.strip()
            if update_in.transaction_date is not None:
                current_tx.transaction_date = update_in.transaction_date
            if update_in.status is not None:
                current_tx.status = update_in.status.value
            if update_in.notes is not None:
                current_tx.notes = update_in.notes
            if update_in.recurrence_type is not None:
                current_tx.recurrence_type = update_in.recurrence_type
            if update_in.recurrence_interval is not None:
                current_tx.recurrence_interval = update_in.recurrence_interval
            if update_in.recurrence_count is not None:
                current_tx.recurrence_count = update_in.recurrence_count
            if update_in.recurrence_end_date is not None:
                current_tx.recurrence_end_date = update_in.recurrence_end_date
            if update_in.installment_number is not None:
                current_tx.installment_number = update_in.installment_number
            if update_in.total_installments is not None:
                current_tx.total_installments = update_in.total_installments

            # 3. Apply new balance effect
            if target_account:
                cls._apply_balance_effect(
                    account=target_account,
                    dest_account=current_dest_account,
                    tx_type=current_tx.type,
                    amount_cents=current_tx.amount_cents,
                    status=current_tx.status,
                    revert=False,
                )

        await db.commit()
        await db.refresh(tx)
        return tx
