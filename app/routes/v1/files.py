import logging
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from app.core.upload_limits import (
    LimitedMultipartParser,
    UploadLimitError,
    is_disk_full,
    limited_stream,
)
from app.services.file_service import FileService, FileUploadError

files_router = APIRouter(prefix="/files", tags=["files"])
logger = logging.getLogger(__name__)


@files_router.post(
    "",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload_file(request: Request):
    settings = request.app.state.settings
    limits = settings.upload_limits
    if request.app.state.active_uploads >= limits.max_concurrent:
        raise HTTPException(status_code=429, detail="Too many simultaneous uploads")
    request.app.state.active_uploads += 1
    parser = None
    form = None
    try:
        if (
            not request.headers.get("content-type", "")
            .lower()
            .startswith("multipart/form-data")
        ):
            raise HTTPException(status_code=422, detail="A multipart file is required")
        max_bytes = limits.max_file_mib * 1024 * 1024
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length < 0:
                    raise ValueError
            except ValueError as error:
                raise HTTPException(
                    status_code=400, detail="Invalid Content-Length"
                ) from error
            if length > max_bytes + 65536:
                raise HTTPException(
                    status_code=413,
                    detail="Upload request exceeds the configured size limit",
                )
        parser = LimitedMultipartParser(
            request.headers,
            limited_stream(
                request, max_bytes=max_bytes, timeout=limits.idle_timeout_seconds
            ),
            max_bytes=max_bytes,
            reserve=limits.reserve_mib * 1024 * 1024,
        )
        form = await parser.parse()
        file = form.get("file")
        if not isinstance(file, UploadFile) or len(form) != 1:
            raise HTTPException(status_code=422, detail="Exactly one file is required")
        service = FileService(storage_dir=settings.transmitter.storage_dir)
        record = await service.upload(
            file, reserve_bytes=limits.reserve_mib * 1024 * 1024
        )
        duration = max(perf_counter() - request.state.started_at, 0.000001)
        return {
            "id": record.id,
            "filename": record.original_name,
            "saved_filename": record.storage_name,
            "size": record.size_bytes,
            "content_type": record.content_type,
            "created_at": record.created_at,
            "upload": {
                "duration_seconds": round(duration, 3),
                "average_speed_bytes_per_second": round(
                    record.size_bytes / duration, 2
                ),
                "remaining_seconds": 0,
            },
        }
    except UploadLimitError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except (MultiPartException, MultipartParseError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OSError as error:
        if is_disk_full(error):
            raise HTTPException(
                status_code=507, detail="Not enough free disk space for this upload"
            ) from error
        raise
    except FileUploadError as error:
        logger.error("Upload request failed: %s", error)
        cause = error.__cause__
        if isinstance(cause, UploadLimitError):
            raise HTTPException(
                status_code=cause.status_code, detail=str(cause)
            ) from error
        if isinstance(cause, OSError) and is_disk_full(cause):
            raise HTTPException(
                status_code=507, detail="Not enough free disk space for this upload"
            ) from error
        raise HTTPException(status_code=500, detail=str(error)) from error
    finally:
        try:
            if form is not None:
                await form.close()
            elif parser is not None:
                for temporary_file in parser._files_to_close_on_error:
                    temporary_file.close()
        finally:
            request.app.state.active_uploads -= 1


@files_router.get("")
async def list_files(): ...


@files_router.get("/{files_id}")
async def get_file(file_id: UUID): ...


@files_router.delete("/{file_id}", status_code=204)
async def delete_fille(file_id: UUID): ...
