from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request

from app.core.db import Database
from app.core.settings import Settings
from app.core.settings import settings as default_settings
from app.routes.api_v1 import api_v1
from app.routes.health import health_router
from app.routes.static import register_static


def create_app(config: Settings | None = None) -> FastAPI:
    config = config or default_settings
    config.transmitter.storage_dir.mkdir(parents=True, exist_ok=True)
    database = Database(
        url=config.transmitter.database_url,
        echo=config.app.debug,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        await application.state.database.dispose()

    app = FastAPI(
        debug=config.app.debug,
        title=config.app.title,
        description=config.app.description,
        version=config.app.version,
        lifespan=lifespan,
    )

    app.state.settings = config
    app.state.database = database

    @app.middleware("http")
    async def request_timer(request: Request, call_next):
        request.state.started_at = perf_counter()
        return await call_next(request)

    app.include_router(router=health_router)
    app.include_router(router=api_v1)
    register_static(app=app)

    return app
