import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.modules.transactions.domain.enums import (
    CategoryType,
    TransactionOrigin,
    TransactionStatus,
    TransactionType,
)


class CategoryCreate(BaseModel):
    """Schema for creating a personal transaction category."""

    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="tag", max_length=50)
    color: str = Field(default="#6B7280", max_length=7)
    type: CategoryType = CategoryType.EXPENSE
    parent_id: uuid.UUID | None = None


class CategoryUpdate(BaseModel):
    """Schema for updating a personal transaction category."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=7)
    type: CategoryType | None = None


class CategoryResponse(BaseModel):
    """Schema for category data response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str
    color: str
    type: str
    is_system_default: bool
    parent_id: uuid.UUID | None = None


class TransactionCreate(BaseModel):
    """Schema for registering a new transaction."""

    account_id: uuid.UUID | None = None
    destination_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    amount_cents: int = Field(..., gt=0, description="Amount in cents, must be positive")
    type: TransactionType = TransactionType.EXPENSE
    description: str = Field(..., min_length=1, max_length=255)
    transaction_date: date = Field(default_factory=date.today)
    settlement_date: date | None = None
    status: TransactionStatus = TransactionStatus.CONFIRMED
    notes: str | None = None
    recurrence_type: str | None = Field(default=None, description="Type of recurrence: daily, weekly, monthly, yearly, installments")
    recurrence_interval: int | None = Field(default=None, description="Interval between occurrences")
    recurrence_count: int | None = Field(default=None, description="Number of occurrences")
    recurrence_end_date: date | None = Field(default=None, description="End date for recurrence")
    installment_number: int | None = Field(default=None, description="Current installment number")
    total_installments: int | None = Field(default=None, description="Total number of installments")

    @model_validator(mode="after")
    def validate_transfer_accounts(self) -> "TransactionCreate":
        if self.type == TransactionType.TRANSFER:
            if not self.destination_account_id:
                raise ValueError("destination_account_id is required for transfers")
            if self.account_id and self.destination_account_id == self.account_id:
                raise ValueError("Source and destination accounts must be different")
        return self


class TransactionUpdate(BaseModel):
    """Schema for updating an existing transaction."""

    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    type: TransactionType | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    transaction_date: date | None = None
    status: TransactionStatus | None = None
    notes: str | None = None
    recurrence_type: str | None = None
    recurrence_interval: int | None = None
    recurrence_count: int | None = None
    recurrence_end_date: date | None = None
    installment_number: int | None = None
    total_installments: int | None = None
    edit_scope: str | None = Field(default=None, description="Edit scope: single, future, all")


class TransactionResponse(BaseModel):
    """Schema for returning transaction details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    destination_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    category_icon: str | None = None
    category_color: str | None = None
    account_name: str | None = None
    amount_cents: int
    type: str
    description: str
    transaction_date: date
    settlement_date: date | None = None
    status: str
    origin: str = TransactionOrigin.MANUAL.value
    external_id: str | None = None
    notes: str | None = None
    recurrence_type: str | None = None
    recurrence_interval: int | None = None
    recurrence_count: int | None = None
    recurrence_end_date: date | None = None
    parent_transaction_id: uuid.UUID | None = None
    installment_number: int | None = None
    total_installments: int | None = None
    created_at: datetime
