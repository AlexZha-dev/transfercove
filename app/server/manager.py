import asyncio
import logging
from contextlib import suppress
from enum import StrEnum
from time import monotonic

import uvicorn
from alembic.util.exc import CommandError
from sqlalchemy.exc import SQLAlchemyError

from app.application import create_app
from app.core.migrations import upgrade_database_async
from app.core.settings import Settings

logger = logging.getLogger(__name__)


class ServerState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ServerError(RuntimeError):
    """Raised when the embedded FastAPI server cannot start."""


class ServerManager:
    def __init__(
        self,
        startup_timeout: float = 15.0,
        shutdown_timeout: float = 10.0,
    ) -> None:
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout

        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self.state = ServerState.STOPPED
        self.error: str | None = None

    @property
    def is_running(self) -> bool:
        return self.state == ServerState.RUNNING

    async def start(self, settings: Settings) -> None:
        async with self._lock:
            if self.is_running:
                return

            if self._task and not self._task.done():
                await self._stop_unlocked()

            self.state = ServerState.STARTING
            self.error = None

            try:
                await upgrade_database_async(settings.transmitter.database_url)

                application = create_app(settings)
                config = uvicorn.Config(
                    app=application,
                    host=settings.uvicorn.host,
                    port=settings.uvicorn.port,
                    log_level=settings.uvicorn.log_level,
                    # Reload starts a second process and is not compatible
                    # with an embedded server controlled by Flet.
                    reload=False,
                    access_log=settings.app.debug,
                )

                self._server = uvicorn.Server(config)
                self._task = asyncio.create_task(
                    self._server.serve(),
                    name="transfercove-fastapi",
                )

                await self._wait_until_ready(settings)
                self.state = ServerState.RUNNING
            except (
                CommandError,
                OSError,
                RuntimeError,
                SQLAlchemyError,
                TimeoutError,
                ValueError,
            ) as error:
                self.error = str(error)
                await self._stop_unlocked()
                self.state = ServerState.ERROR
                raise ServerError(str(error)) from error

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        server = self._server
        task = self._task

        if server is None or task is None:
            self._clear_task()
            self.state = ServerState.STOPPED
            return

        self.state = ServerState.STOPPING
        server.should_exit = True

        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=self.shutdown_timeout,
            )
        except TimeoutError:
            server.force_exit = True
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        except asyncio.CancelledError:
            logger.debug("FastAPI server task was cancelled while stopping")
        except (
            CommandError,
            OSError,
            RuntimeError,
            SQLAlchemyError,
            ValueError,
        ):
            # The server task is being stopped; its original exception is
            # reported by start() when startup fails.
            logger.exception("FastAPI server task failed while stopping")
        finally:
            self._clear_task()
            self.state = ServerState.STOPPED

    def _clear_task(self) -> None:
        self._server = None
        self._task = None

    async def _wait_until_ready(self, settings: Settings) -> None:
        deadline = monotonic() + self.startup_timeout

        while monotonic() < deadline:
            task = self._task
            if task is None:
                raise RuntimeError("FastAPI server task was not created")

            if task.done():
                with suppress(asyncio.CancelledError):
                    task_error = task.exception()
                    if task_error is not None:
                        raise RuntimeError(
                            "FastAPI server stopped during startup"
                        ) from task_error
                raise RuntimeError("FastAPI server stopped during startup")

            if await self._healthcheck(settings):
                return

            await asyncio.sleep(0.1)

        raise TimeoutError(
            f"FastAPI did not become ready within {self.startup_timeout:g} seconds"
        )

    async def _healthcheck(self, settings: Settings) -> bool:
        host = settings.uvicorn.host
        if host in {"", "0.0.0.0", "*"}:
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"

        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, settings.uvicorn.port),
                timeout=0.5,
            )
            writer.write(
                (
                    f"GET /health HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
                ).encode()
            )
            await writer.drain()
            response = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            return response.startswith((b"HTTP/1.1 200", b"HTTP/1.0 200"))
        except (OSError, TimeoutError):
            return False
        finally:
            if writer is not None:
                writer.close()
                with suppress(OSError, TimeoutError):
                    await writer.wait_closed()
