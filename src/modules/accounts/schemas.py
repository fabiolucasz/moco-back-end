import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.modules.accounts.domain.enums import AccountType


class AccountCreate(BaseModel):
    """Schema for creating a financial account or physical cash wallet."""

    name: str = Field(..., min_length=1, max_length=100, description="Account or wallet name")
    account_type: AccountType = Field(default=AccountType.CHECKING, description="Account type")
    initial_balance_cents: int = Field(default=0, description="Initial balance in cents")
    currency: str = Field(default="BRL", max_length=3, description="ISO 4217 currency code")
    color: str = Field(default="#0066FF", max_length=7, description="HEX color tag")


class AccountUpdate(BaseModel):
    """Schema for updating an existing account."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    account_type: AccountType | None = None
    color: str | None = Field(default=None, max_length=7)


class AccountResponse(BaseModel):
    """Schema for returning account details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: str
    balance_cents: int
    currency: str
    color: str
    is_manual: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
