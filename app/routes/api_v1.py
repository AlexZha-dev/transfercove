from fastapi import APIRouter

from app.routes.v1.files import files_router

api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(files_router)
