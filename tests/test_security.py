from datetime import timedelta

import pytest

from src.core.exceptions import UnauthorizedError
from src.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    """Verifies that Argon2 password hashing and verification function correctly."""
    raw_password = "super-secure-password-123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$argon2")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_access_token_creation_and_decoding() -> None:
    """Verifies JWT access token generation and payload extraction."""
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token = create_access_token(subject=user_id, extra_claims={"email": "user@example.com"})

    payload = decode_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "access"


def test_jwt_expired_token_raises_unauthorized() -> None:
    """Verifies that an expired JWT token raises UnauthorizedError."""
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    # Token expired 10 minutes ago
    expired_token = create_access_token(subject=user_id, expires_delta=timedelta(minutes=-10))

    with pytest.raises(UnauthorizedError, match="Token has expired"):
        decode_token(expired_token)
