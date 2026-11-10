from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.identity.dependencies import get_current_active_user
from src.modules.identity.models import User
from src.modules.identity.schemas import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from src.modules.identity.services import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Creates a new user account with email and password."""
    return await AuthService.register_user(db, user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with email and password",
)
async def login(
    login_in: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Authenticates user credentials and returns JWT access and refresh tokens."""
    user, access_token, refresh_token = await AuthService.authenticate_local(
        db, login_in
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Renew access token using rotating refresh token",
)
async def refresh_token(
    refresh_in: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Rotates refresh token and issues a new token pair."""
    new_access, new_refresh, user = await AuthService.refresh_session(
        db, refresh_in.refresh_token
    )
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate or register using Google OAuth ID token",
)
async def google_login(
    google_in: GoogleLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Verifies Google ID token, registers or logs in user, and issues a token pair."""
    user, access_token, refresh_token = await AuthService.authenticate_google(
        db, google_in.id_token
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out and revoke refresh token session",
)
async def logout(
    refresh_in: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Invalidates the provided refresh token session."""
    await AuthService.revoke_session(db, refresh_in.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Returns the profile of the currently logged-in user."""
    return current_user
