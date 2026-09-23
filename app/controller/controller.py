from collections.abc import Callable

from app.core.settings import Settings
from app.core.settings_store import SettingsStore
from app.server.manager import ServerError, ServerManager, ServerState


class AppController:
    def __init__(self) -> None:
        self.settings_store = SettingsStore()
        self.server_manager = ServerManager()
        self.settings = Settings()

        self.initialized = False
        self.listeners: list[Callable[[], None]] = []
        self.last_error: str | None = None

    async def initialize(self) -> None:
        self.settings = await self.settings_store.load(self.settings)
        self.initialized = True
        self.notify()

    @property
    def server_url(self) -> str:
        host = self.settings.uvicorn.host
        display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        return f"http://{display_host}:{self.settings.uvicorn.port}/"

    @property
    def health_url(self) -> str:
        return f"{self.server_url.rstrip('/')}/health"

    @property
    def server_state(self) -> ServerState:
        return self.server_manager.state

    @property
    def server_running(self) -> bool:
        return self.server_manager.is_running

    def subscribe(self, listener: Callable[[], None]) -> None:
        self.listeners.append(listener)

    def notify(self) -> None:
        for listener in self.listeners:
            listener()

    async def start_server(self) -> bool:
        if not self.initialized:
            return False

        self.last_error = None
        self.server_manager.state = ServerState.STARTING
        self.notify()

        try:
            await self.server_manager.start(self.settings)
        except ServerError as error:
            self.last_error = str(error)
            self.notify()
            return False

        self.notify()
        return True

    async def stop_server(self) -> None:
        self.server_manager.state = ServerState.STOPPING
        self.notify()
        await self.server_manager.stop()
        self.notify()

    async def save_settings(self, settings: Settings) -> bool:
        restart_required = self.server_running
        if restart_required:
            await self.stop_server()

        self.settings = await self.settings_store.save(settings)
        self.notify()

        if restart_required:
            return await self.start_server()

        return True

    async def close(self) -> None:
        await self.server_manager.stop()
        await self.settings_store.close()
