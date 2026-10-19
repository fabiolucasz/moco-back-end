from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.config import get_settings
from src.core.database import engine
from src.core.exceptions import register_exception_handlers
from src.core.logging import setup_logging
from src.core.middleware import register_middlewares
from src.modules.accounts.router import router as accounts_router
from src.modules.identity.router import router as auth_router
from src.modules.transactions.router import categories_router, transactions_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan context manager for startup and shutdown routines."""
    setup_logging()
    yield
    # Cleanup database engine connections on shutdown
    await engine.dispose()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="FinPilot API — Plataforma SaaS de Gestão e Inteligência Financeira Pessoal",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global middlewares and error handling
    register_middlewares(app)
    register_exception_handlers(app)

    # API Routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(accounts_router, prefix="/api/v1")
    app.include_router(categories_router, prefix="/api/v1")
    app.include_router(transactions_router, prefix="/api/v1")

    @app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
    async def health_check() -> dict[str, Any]:
        """Health check endpoint validating application and database responsiveness."""
        db_status = "unhealthy"
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as e:
            db_status = f"unavailable: {str(e)}"

        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
            "database": db_status,
        }

    return app


app = create_app()
