from enum import StrEnum


class TransactionType(StrEnum):
    """Direction or nature of a transaction."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class TransactionStatus(StrEnum):
    """Lifecycle status of a transaction."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"


class TransactionOrigin(StrEnum):
    """Source of transaction entry."""

    MANUAL = "manual"
    OPEN_FINANCE = "open_finance"


class CategoryType(StrEnum):
    """Classification type of a category."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
