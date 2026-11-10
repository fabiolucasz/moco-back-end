import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class FinancialAccount(Base):
    """Financial account or physical cash wallet owned by a user."""

    __tablename__ = "financial_accounts"

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
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    balance_cents: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="BRL",
        nullable=False,
    )
    color: Mapped[str] = mapped_column(
        String(7),
        default="#0066FF",
        nullable=False,
    )
    is_manual: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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
