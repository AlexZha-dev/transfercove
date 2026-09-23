from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.services.file_service import FileService

files_router = APIRouter(prefix="/files", tags=["files"])


SessionDependency = Annotated[AsyncSession, Depends(get_session)]

@files_router.post("")
async def upload_file(
    file: UploadFile,
    session: SessionDependency,
    request: Request,
):
    service = FileService(
        session=session,
        storage_dir=request.app.state.settings.transmitter.storage_dir,
    )

    record = await service.upload(file)

    duration = max(perf_counter() - request.state.started_at, 0.000001)
    speed = record.size_bytes / duration

    return {
        "id": record.id,
        "filename": record.original_name,
        "size": record.size_bytes,
        "content_type": record.content_type,
        "created_at": record.created_at,
        "upload": {
            "duration_seconds": round(duration, 3),
            "average_speed_bytes_per_second": round(speed, 2),
            "remaining_seconds": 0,
        },
    }


@files_router.get("")
async def list_files(): ...


@files_router.get("/{files_id}")
async def get_file(file_id: UUID): ...


@files_router.delete("/{file_id}", status_code=204)
async def delete_fille(file_id: UUID): ...
