from fastapi import FastAPI

from app.core.settings import settings as s
from app.routes.api_v1 import api_v1
from app.routes.health import health_router

app = FastAPI(
    debug=s.app.debug,
    title=s.app.title,
    description=s.app.description,
    version=s.app.version,
)

app.include_router(router=health_router)
app.include_router(router=api_v1)
