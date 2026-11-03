import uuid
from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.identity.dependencies import get_current_active_user
from src.modules.identity.models import User
from src.modules.transactions.domain.enums import CategoryType, TransactionType
from src.modules.transactions.models import Transaction, TransactionCategory
from src.modules.transactions.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from src.modules.transactions.services import CategoryService, TransactionService

categories_router = APIRouter(prefix="/categories", tags=["Transaction Categories"])
transactions_router = APIRouter(prefix="/transactions", tags=["Transactions"])


# ==============================================================================
# Categories Endpoints
# ==============================================================================


@categories_router.get(
    "",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List available categories (system defaults + personal)",
)
async def list_categories(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    category_type: Annotated[CategoryType | None, Query(alias="type")] = None,
) -> Sequence[TransactionCategory]:
    """Returns all system categories and custom categories created by the user."""
    # Ensure system categories are seeded
    await CategoryService.seed_system_categories(db)
    return await CategoryService.list_categories(db, current_user.id, category_type)


@categories_router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom personal category",
)
async def create_category(
    cat_in: CategoryCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionCategory:
    """Creates a custom transaction category for the authenticated user."""
    return await CategoryService.create_custom_category(db, current_user.id, cat_in)


@categories_router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a custom personal category",
)
async def update_category(
    category_id: uuid.UUID,
    cat_update: CategoryUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionCategory:
    """Updates a custom category owned by the authenticated user."""
    return await CategoryService.update_custom_category(
        db, current_user.id, category_id, cat_update
    )


@categories_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom personal category",
)
async def delete_category(
    category_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Deletes a custom category and detaches transactions that use it."""
    await CategoryService.delete_custom_category(db, current_user.id, category_id)


# ==============================================================================
# Transactions Endpoints
# ==============================================================================


@transactions_router.get(
    "",
    response_model=list[TransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="List transactions with filters and pagination",
)
async def list_transactions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    tx_type: Annotated[TransactionType | None, Query(alias="type")] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Transaction]:
    """Retrieves transactions owned by the user, ordered by date descending."""
    return await TransactionService.list_transactions(
        db=db,
        user_id=current_user.id,
        account_id=account_id,
        category_id=category_id,
        tx_type=tx_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@transactions_router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new transaction (income, expense, or transfer)",
)
async def create_transaction(
    tx_in: TransactionCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Transaction:
    """Registers a transaction and atomically updates the associated account balance."""
    return await TransactionService.create_transaction(db, current_user.id, tx_in)


@transactions_router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transaction details by ID",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Transaction:
    """Retrieves a single transaction verifying user ownership."""
    return await TransactionService.get_transaction(db, current_user.id, transaction_id)


@transactions_router.put(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transaction details and reconcile balances",
)
async def update_transaction(
    transaction_id: uuid.UUID,
    update_in: TransactionUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Transaction:
    """Updates transaction and recalculates account balances accurately."""
    return await TransactionService.update_transaction(
        db, current_user.id, transaction_id, update_in
    )


@transactions_router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction and reverse its balance impact",
)
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Deletes a transaction and restores the previous account balance."""
    await TransactionService.delete_transaction(db, current_user.id, transaction_id)
