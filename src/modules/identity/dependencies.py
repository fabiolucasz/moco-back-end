import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import UnauthorizedError
from src.core.security import decode_token
from src.modules.identity.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Extracts and validates the authenticated user from the Bearer JWT."""
    if not token:
        raise UnauthorizedError("Missing authentication token")

    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError("Malformed authentication token")

    try:
        user_uuid = uuid.UUID(subject)
    except ValueError as err:
        raise UnauthorizedError("Invalid user identity in token") from err

    user = await db.get(User, user_uuid)
    if not user:
        raise UnauthorizedError("User does not exist")

    if not user.is_active:
        raise UnauthorizedError("User account is inactive")

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensures the current user is active."""
    return current_user
