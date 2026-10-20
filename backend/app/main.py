from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.database import migrate
from app.errors import register_error_handlers
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.jobs import router as jobs_router
from app.routers.parsing import router as parsing_router
from app.routers.preferences import router as preferences_router
from app.routers.stats import router as stats_router
from app.services.admin_bootstrap import ensure_admin


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.auto_migrate:
        if not settings.jwt_key:
            raise RuntimeError("JWT_KEY must be configured.")
        migrate()
        ensure_admin()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SufferTracker",
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_dev else None,
        lifespan=lifespan,
    )
    origins = [item.strip() for item in settings.frontend_origin.split(";") if item.strip()]
    origins.extend(["http://localhost:4200", "http://127.0.0.1:4200"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys(origins)),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(parsing_router)
    app.include_router(jobs_router)
    app.include_router(preferences_router)
    app.include_router(stats_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.is_dev:
        @app.get("/swagger", include_in_schema=False)
        def swagger() -> RedirectResponse:
            return RedirectResponse("/docs")

    return app


app = create_app()
