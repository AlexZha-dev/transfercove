import asyncio
import errno
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import BinaryIO, TypeVar

from anyio import CancelScope
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

T = TypeVar("T")


async def run_disk_io(operation: Callable[..., T], *args) -> T:
    """Finish in-flight I/O before cancellation lets the caller close its file."""
    cancellation = None
    with CancelScope(shield=True):
        task = asyncio.create_task(asyncio.to_thread(operation, *args))
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError as error:
                if task.cancelled():
                    raise
                cancellation = error
            except Exception:
                if cancellation is not None:
                    raise cancellation
                raise
    if cancellation is not None:
        raise cancellation
    return result


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


class DiskSpaceGuard:
    """Serialize this server's space checks and writes, including buffer flushes."""

    def __init__(self) -> None:
        self._lock = Lock()

    async def check(self, path: Path, reserve: int) -> None:
        await run_disk_io(check_space, path, reserve)

    async def write(
        self,
        file: BinaryIO,
        path: Path,
        reserve: int,
        data: bytes,
        *,
        incoming: int | None = None,
    ) -> None:
        await run_disk_io(
            self._write,
            file,
            path,
            reserve,
            data,
            len(data) if incoming is None else incoming,
        )

    def _write(self, file, path, reserve, data, incoming) -> None:
        with self._lock:
            check_space(path, reserve, incoming)
            file.write(data)
            # Publish buffered writes to the OS before another upload checks space.
            file.flush()


class GuardedUploadFile(UploadFile):
    def __init__(self, upload: UploadFile, guard: DiskSpaceGuard, reserve: int):
        super().__init__(
            upload.file,
            size=upload.size,
            filename=upload.filename,
            headers=upload.headers,
        )
        self.guard = guard
        self.reserve = reserve
        self.temp_dir = Path(tempfile.gettempdir())

    async def write(self, data: bytes) -> None:
        if not self._will_roll(len(data)):
            await super().write(data)
            return
        # Rollover writes the entire in-memory buffer, not only the new data.
        incoming = len(data) + (self.file.tell() if self._in_memory else 0)
        await self.guard.write(
            self.file, self.temp_dir, self.reserve, data, incoming=incoming
        )
        if self.size is not None:
            self.size += len(data)

    async def read(self, size: int = -1) -> bytes:
        if self._in_memory:
            return await super().read(size)
        return await run_disk_io(self.file.read, size)

    async def seek(self, offset: int) -> None:
        if self._in_memory:
            await super().seek(offset)
        else:
            await run_disk_io(self.file.seek, offset)

    async def close(self) -> None:
        if self._in_memory:
            await super().close()
        else:
            await run_disk_io(self.file.close)


class LimitedMultipartParser(MultiPartParser):
    def __init__(
        self,
        headers,
        stream,
        *,
        max_bytes: int,
        reserve: int,
        disk_guard: DiskSpaceGuard | None = None,
    ):
        super().__init__(headers, stream, max_files=1, max_fields=0)
        self.max_bytes = max_bytes
        self.reserve = reserve
        self.file_bytes = 0
        self.disk_guard = disk_guard or DiskSpaceGuard()
        self._finished = False

    async def parse(self) -> FormData:
        try:
            await self.disk_guard.check(Path(tempfile.gettempdir()), self.reserve)
            form = await super().parse()
            # python-multipart's finalize() does not validate the final boundary.
            if not self._finished:
                raise MultiPartException("Incomplete multipart upload")
            return form
        except BaseException:
            await self.close()
            raise

    def on_end(self) -> None:
        self._finished = True

    async def close(self) -> None:
        # Incomplete parts are not in FormData, but still own temporary files.
        await run_disk_io(self._close_files)

    def _close_files(self) -> None:
        first_error = None
        for file in self._files_to_close_on_error:
            try:
                file.close()
            except OSError as error:
                first_error = first_error or error
        if first_error is not None:
            raise first_error

    def on_headers_finished(self) -> None:
        super().on_headers_finished()
        if self._current_part.file is not None:
            self._current_part.file = GuardedUploadFile(
                self._current_part.file, self.disk_guard, self.reserve
            )

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            length = end - start
            self.file_bytes += length
            if self.file_bytes > self.max_bytes:
                raise UploadLimitError(413, "File exceeds the configured size limit")
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
