import asyncio
import errno
import shutil
import tempfile
from pathlib import Path

from starlette.formparsers import MultiPartException, MultiPartParser


class UploadLimitError(MultiPartException):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def check_space(path: Path, reserve: int, incoming: int = 0) -> None:
    try:
        free = shutil.disk_usage(path).free
    except OSError as error:
        raise UploadLimitError(507, "Cannot check available disk space") from error
    if free < reserve + incoming:
        raise UploadLimitError(507, "Not enough free disk space for this upload")


def is_disk_full(error: OSError) -> bool:
    return error.errno in {errno.ENOSPC, errno.EDQUOT} or getattr(
        error, "winerror", None
    ) in {39, 112}


class LimitedMultipartParser(MultiPartParser):
    def __init__(self, headers, stream, *, max_bytes: int, reserve: int):
        super().__init__(headers, stream, max_files=1, max_fields=0)
        self.max_bytes = max_bytes
        self.reserve = reserve
        self.file_bytes = 0
        check_space(Path(tempfile.gettempdir()), reserve)

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            length = end - start
            self.file_bytes += length
            if self.file_bytes > self.max_bytes:
                raise UploadLimitError(413, "File exceeds the configured size limit")
            check_space(Path(tempfile.gettempdir()), self.reserve, length)
        super().on_part_data(data, start, end)


async def limited_stream(request, *, max_bytes: int, timeout: int):
    iterator = request.stream().__aiter__()
    total = 0
    while True:
        try:
            chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
        except StopAsyncIteration:
            return
        except TimeoutError as error:
            raise UploadLimitError(
                408, "Upload timed out while waiting for data"
            ) from error
        total += len(chunk)
        if total > max_bytes + 65536:
            raise UploadLimitError(
                413, "Upload request exceeds the configured size limit"
            )
        yield chunk
