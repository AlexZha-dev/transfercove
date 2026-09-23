from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

static_router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"


@static_router.get("/")
async def upload_file():
    return FileResponse(BASE_DIR / "static" / "upload.html")


def register_static(app: FastAPI) -> None:
    app.include_router(static_router)
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )
