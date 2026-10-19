import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.modules.analytics.schemas import DashboardResponse
from src.modules.analytics.services import DashboardService
from src.modules.identity.dependencies import get_current_active_user
from src.modules.identity.models import User

router = APIRouter(prefix="/analytics", tags=["Financial Analytics & Dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated financial metrics and dashboard summary",
)
async def get_dashboard(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    account_id: uuid.UUID | None = None,
) -> DashboardResponse:
    """Computes consolidated balance, monthly totals, category spending, and comparison."""
    return await DashboardService.get_dashboard(
        db=db,
        user_id=current_user.id,
        year=year,
        month=month,
        account_id=account_id,
    )
