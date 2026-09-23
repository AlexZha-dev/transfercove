from uuid import UUID

from fastapi import APIRouter
from starlette.datastructures import UploadFile

files_router = APIRouter(prefix="/files", tags=["files"])


@files_router.post("")
async def upload_file(file: UploadFile): ...


@files_router.get("")
async def list_files(): ...


@files_router.get("/{files_id}")
async def get_file(file_id: UUID): ...


@files_router.delete("/{file_id}", status_code=204)
async def delete_fille(file_id: UUID): ...
