from enum import StrEnum


class AccountType(StrEnum):
    """Types of financial accounts supported."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CASH_WALLET = "cash_wallet"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
