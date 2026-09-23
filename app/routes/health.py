from fastapi import APIRouter

health_router = APIRouter()


@health_router.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok"}
