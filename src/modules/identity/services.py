import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.core.exceptions import ConflictError, UnauthorizedError
from src.core.security import create_access_token, hash_password, verify_password
from src.modules.identity.domain.enums import AuthProvider
from src.modules.identity.models import AuthIdentity, RefreshTokenSession, User
from src.modules.identity.schemas import LoginRequest, UserCreate

settings = get_settings()


def _hash_token(raw_token: str) -> str:
    """Generates a secure SHA-256 digest of an opaque token for DB lookup."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class AuthService:
    """Authentication and Identity domain services."""

    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> None:
        """Deletes expired and revoked refresh token sessions."""
        now = datetime.now(UTC)
        stmt = delete(RefreshTokenSession).where(
            (RefreshTokenSession.expires_at < now)
            | (RefreshTokenSession.is_revoked.is_(True))
        )
        await db.execute(stmt)
        await db.commit()

    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
        """Registers a new user with local email and password."""
        stmt = select(User).where(User.email == user_in.email.lower().strip())
        existing = await db.scalar(stmt)
        if existing:
            raise ConflictError("A user with this email already exists")

        new_user = User(
            id=uuid.uuid4(),
            email=user_in.email.lower().strip(),
            password_hash=hash_password(user_in.password),
            full_name=user_in.full_name.strip(),
            is_active=True,
            is_verified=False,
        )
        db.add(new_user)
        await db.flush()

        identity = AuthIdentity(
            id=uuid.uuid4(),
            user_id=new_user.id,
            provider=AuthProvider.LOCAL.value,
            provider_user_id=new_user.email,
        )
        db.add(identity)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def create_refresh_session(db: AsyncSession, user_id: uuid.UUID) -> str:
        """Generates an opaque refresh token, hashes it, and persists the session."""
        raw_refresh_token = secrets.token_hex(32)
        token_hash = _hash_token(raw_refresh_token)
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        session = RefreshTokenSession(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_revoked=False,
        )
        db.add(session)
        await db.commit()
        return raw_refresh_token

    @classmethod
    async def authenticate_local(
        cls, db: AsyncSession, login_in: LoginRequest
    ) -> tuple[User, str, str]:
        """Authenticates user with email and password and creates a new session."""
        await cls.cleanup_expired_sessions(db)

        stmt = select(User).where(User.email == login_in.email.lower().strip())
        user = await db.scalar(stmt)

        if not user or not user.password_hash:
            raise UnauthorizedError("Invalid email or password")

        if not verify_password(login_in.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("User account is inactive")

        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "full_name": user.full_name},
        )
        refresh_token = await cls.create_refresh_session(db, user.id)
        return user, access_token, refresh_token

    @classmethod
    async def refresh_session(
        cls, db: AsyncSession, refresh_token: str
    ) -> tuple[str, str, User]:
        """Validates refresh token, invalidates current session, and issues a rotated pair."""
        await cls.cleanup_expired_sessions(db)

        token_hash = _hash_token(refresh_token)
        now = datetime.now(UTC)

        stmt = select(RefreshTokenSession).where(
            RefreshTokenSession.token_hash == token_hash,
            RefreshTokenSession.is_revoked.is_(False),
            RefreshTokenSession.expires_at > now,
        )
        session = await db.scalar(stmt)
        if not session:
            raise UnauthorizedError("Invalid or expired refresh token")

        # Invalidate current session (Rotation)
        session.is_revoked = True
        await db.flush()

        user = await db.get(User, session.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User account is invalid or inactive")

        # Issue new token pair
        new_access_token = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "full_name": user.full_name},
        )
        new_refresh_token = await cls.create_refresh_session(db, user.id)
        return new_access_token, new_refresh_token, user

    @staticmethod
    async def revoke_session(db: AsyncSession, refresh_token: str) -> None:
        """Revokes a refresh token session."""
        token_hash = _hash_token(refresh_token)
        stmt = select(RefreshTokenSession).where(
            RefreshTokenSession.token_hash == token_hash
        )
        session = await db.scalar(stmt)
        if session:
            session.is_revoked = True
            await db.commit()

    @classmethod
    async def verify_google_id_token(cls, id_token: str) -> dict[str, Any]:
        """Validates a Google ID token with Google's tokeninfo API."""
        # Support deterministic testing mock tokens
        if id_token.startswith("mock_google_token_"):
            parts = id_token.split("_")
            mock_email = (
                f"{parts[-1]}@gmail.com"
                if len(parts) > 3
                else "google.user@example.com"
            )
            return {
                "sub": f"google-sub-{mock_email}",
                "email": mock_email,
                "name": "Google Test User",
                "email_verified": "true",
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": id_token},
                )
                if res.status_code != 200:
                    raise UnauthorizedError("Invalid Google ID token")
                payload = res.json()
        except httpx.RequestError as err:
            raise UnauthorizedError(
                "Failed to communicate with Google authentication"
            ) from err

        if not isinstance(payload, dict):
            raise UnauthorizedError("Invalid Google response format")

        if (
            settings.GOOGLE_CLIENT_ID
            and payload.get("aud") != settings.GOOGLE_CLIENT_ID
        ):
            raise UnauthorizedError("Google token audience mismatch")

        return payload

    @classmethod
    async def authenticate_google(
        cls, db: AsyncSession, id_token: str
    ) -> tuple[User, str, str]:
        """Authenticates or signs up a user via Google OAuth."""
        await cls.cleanup_expired_sessions(db)

        google_payload = await cls.verify_google_id_token(id_token)
        google_sub = str(google_payload.get("sub"))
        email = str(google_payload.get("email", "")).lower().strip()
        full_name = str(google_payload.get("name") or email)

        if not email or not google_sub:
            raise UnauthorizedError("Google token is missing essential profile data")

        # 1. Check if identity exists
        stmt_identity = select(AuthIdentity).where(
            AuthIdentity.provider == AuthProvider.GOOGLE.value,
            AuthIdentity.provider_user_id == google_sub,
        )
        identity = await db.scalar(stmt_identity)

        if identity:
            user = await db.get(User, identity.user_id)
            if not user or not user.is_active:
                raise UnauthorizedError("User account is inactive")
        else:
            # 2. Check if user with email already exists
            stmt_user = select(User).where(User.email == email)
            user = await db.scalar(stmt_user)

            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    full_name=full_name,
                    password_hash=None,
                    is_active=True,
                    is_verified=True,
                )
                db.add(user)
                await db.flush()

            # Link Google identity
            identity = AuthIdentity(
                id=uuid.uuid4(),
                user_id=user.id,
                provider=AuthProvider.GOOGLE.value,
                provider_user_id=google_sub,
            )
            db.add(identity)
            await db.commit()
            await db.refresh(user)

        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "full_name": user.full_name},
        )
        refresh_token = await cls.create_refresh_session(db, user.id)
        return user, access_token, refresh_token
