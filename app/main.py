from time import perf_counter

from fastapi import FastAPI, Request

from app.core.settings import settings as s
from app.routes.api_v1 import api_v1
from app.routes.health import health_router

app = FastAPI(
    debug=s.app.debug,
    title=s.app.title,
    description=s.app.description,
    version=s.app.version,
)


@app.middleware("http")
async def request_timer(request: Request, call_next):
    request.state.started_at = perf_counter()
    return await call_next(request)


app.include_router(router=health_router)
app.include_router(router=api_v1)
