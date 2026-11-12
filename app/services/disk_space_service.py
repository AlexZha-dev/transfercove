import asyncio
import errno
import shutil
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Protocol, TypeVar

from anyio import CancelScope

T = TypeVar("T")

DISK_FULL_MESSAGE = "Not enough free disk space for this upload"


class WritableBinaryFile(Protocol):
    def write(self, data: bytes, /) -> int: ...

    def flush(self) -> None: ...


class DiskSpaceError(RuntimeError):
    """Raised when disk space is insufficient or cannot be determined."""


async def run_disk_io(operation: Callable[..., T], *args) -> T:
    """Finish in-flight I/O before cancellation lets the caller close its file."""
    cancellation = None
    with CancelScope(shield=True):
        task = asyncio.create_task(asyncio.to_thread(operation, *args))
        while not task.done():
            try:
                await asyncio.shield(task)
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
    return task.result()


def check_space(path: Path, reserve: int, incoming: int = 0) -> None:
    try:
        free = shutil.disk_usage(path).free
    except OSError as error:
        raise DiskSpaceError("Cannot check available disk space") from error
    if free < reserve + incoming:
        raise DiskSpaceError(DISK_FULL_MESSAGE)


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
        file: WritableBinaryFile,
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

    def _write(
        self,
        file: WritableBinaryFile,
        path: Path,
        reserve: int,
        data: bytes,
        incoming: int,
    ) -> None:
        with self._lock:
            check_space(path, reserve, incoming)
            file.write(data)
            # Publish buffered writes to the OS before another upload checks space.
            file.flush()
