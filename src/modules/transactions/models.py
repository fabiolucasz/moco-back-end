import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.modules.accounts.models import FinancialAccount


class TransactionCategory(Base):
    """Classification category for transactions."""

    __tablename__ = "transaction_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("transaction_categories.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    icon: Mapped[str] = mapped_column(
        String(50),
        default="tag",
        nullable=False,
    )
    color: Mapped[str] = mapped_column(
        String(7),
        default="#6B7280",
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    is_system_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="category",
        lazy="selectin",
    )


class Transaction(Base):
    """Financial movement entry (income, expense, transfer)."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    destination_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("transaction_categories.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    transaction_date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
        nullable=False,
    )
    settlement_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="confirmed",
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(
        String(20),
        default="manual",
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    account: Mapped[FinancialAccount] = relationship(
        "FinancialAccount",
        foreign_keys=[account_id],
        lazy="selectin",
    )
    destination_account: Mapped[FinancialAccount | None] = relationship(
        "FinancialAccount",
        foreign_keys=[destination_account_id],
        lazy="selectin",
    )
    category: Mapped[TransactionCategory | None] = relationship(
        "TransactionCategory",
        back_populates="transactions",
        lazy="selectin",
    )

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    @property
    def category_icon(self) -> str | None:
        return self.category.icon if self.category else None

    @property
    def category_color(self) -> str | None:
        return self.category.color if self.category else None

    @property
    def account_name(self) -> str | None:
        return self.account.name if self.account else None
