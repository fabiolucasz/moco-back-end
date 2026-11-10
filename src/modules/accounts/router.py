import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.accounts.models import FinancialAccount
from src.modules.accounts.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from src.modules.accounts.services import AccountService
from src.modules.identity.dependencies import get_current_active_user
from src.modules.identity.models import User

router = APIRouter(prefix="/accounts", tags=["Financial Accounts & Cash Wallets"])


@router.get(
    "",
    response_model=list[AccountResponse],
    status_code=status.HTTP_200_OK,
    summary="List all active accounts and cash wallets for current user",
)
async def list_accounts(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Sequence[FinancialAccount]:
    """Retrieves all accounts owned by the authenticated user."""
    return await AccountService.list_accounts(db, current_user.id)


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account or physical cash wallet",
)
async def create_account(
    account_in: AccountCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FinancialAccount:
    """Creates a new financial account or physical cash wallet."""
    return await AccountService.create_account(db, current_user.id, account_in)


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get account details by ID",
)
async def get_account(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FinancialAccount:
    """Retrieves an account verifying user ownership."""
    return await AccountService.get_account(db, current_user.id, account_id)


@router.put(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an existing account",
)
async def update_account(
    account_id: uuid.UUID,
    update_in: AccountUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FinancialAccount:
    """Updates account fields verifying user ownership."""
    return await AccountService.update_account(
        db, current_user.id, account_id, update_in
    )


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an account",
)
async def delete_account(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Deactivates an account verifying user ownership."""
    await AccountService.deactivate_account(db, current_user.id, account_id)
