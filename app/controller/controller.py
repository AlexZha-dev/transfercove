from collections.abc import Callable

from app.core.settings import Settings
from app.core.settings_store import SettingsStore


class AppController:
    def __init__(self) -> None:
        self.settings_store = SettingsStore()
        self.settings = Settings()

        self.server_running = False
        self.initialized = False
        self.listeners: list[Callable[[], None]] = []

    async def initialize(self) -> None:
        self.settings = await self.settings_store.load(self.settings)
        self.initialized = True
        self.notify()

    @property
    def server_url(self) -> str:
        host = self.settings.uvicorn.host
        display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        return f"http://{display_host}:{self.settings.uvicorn.port}/"

    def subscribe(self, listener: Callable[[], None]) -> None:
        self.listeners.append(listener)

    def notify(self) -> None:
        for listener in self.listeners:
            listener()

    def start_server(self) -> None:
        # Temporary mock until the FastAPI controller is connected.
        self.server_running = True
        self.notify()

    def stop_server(self) -> None:
        # Temporary mock until the FastAPI controller is connected.
        self.server_running = False
        self.notify()

    async def save_settings(self, settings: Settings) -> None:
        self.settings = await self.settings_store.save(settings)
        self.notify()

    async def close(self) -> None:
        await self.settings_store.close()
