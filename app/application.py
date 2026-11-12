from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request

from app.core.migrations import cleanup_legacy_history_async
from app.core.settings import Settings, is_packaged_build
from app.core.settings import settings as default_settings
from app.routes.api_v1 import api_v1
from app.routes.health import health_router
from app.routes.static import register_static
from app.services.disk_space_service import DiskSpaceGuard


def create_app(
    config: Settings | None = None, *, cleanup_on_startup: bool = True
) -> FastAPI:
    config = config or default_settings
    config.transmitter.storage_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if cleanup_on_startup:
            await cleanup_legacy_history_async(config.transmitter.database_url)
        yield

    app = FastAPI(
        debug=config.app.debug,
        title=config.app.title,
        description=config.app.description,
        version=config.app.version,
        lifespan=lifespan,
        docs_url=None if is_packaged_build() else "/docs",
        redoc_url=None if is_packaged_build() else "/redoc",
        openapi_url=None if is_packaged_build() else "/openapi.json",
    )

    app.state.settings = config
    app.state.active_uploads = 0
    app.state.disk_space_guard = DiskSpaceGuard()

    @app.middleware("http")
    async def request_timer(request: Request, call_next):
        request.state.started_at = perf_counter()
        return await call_next(request)

    app.include_router(router=health_router)
    app.include_router(router=api_v1)
    register_static(app=app)

    return app
