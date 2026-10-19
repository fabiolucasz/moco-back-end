from enum import StrEnum


class AuthProvider(StrEnum):
    """Authentication providers supported by FinPilot."""

    LOCAL = "local"
    GOOGLE = "google"
