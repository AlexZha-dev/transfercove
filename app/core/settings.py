import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_storage_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path

    app_data = os.getenv("FLET_APP_STORAGE_DATA")
    base_dir = Path(app_data) if app_data else Path.cwd()
    return (base_dir / path).resolve()


def is_packaged_build() -> bool:
    """Return whether the app is running inside Flet's production bundle."""

    return bool(os.getenv("FLET_APP_CONSOLE"))


def is_windows_packaged_build() -> bool:
    """Return whether this is the installed Windows desktop application."""

    return sys.platform == "win32" and is_packaged_build()


class AppConfig(BaseModel):
    title: str = "TransferCove"
    description: str = "Application for sharing files over a local network"
    version: str = "0.3.2"
    debug: bool = False


class UvicornConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "info"
    reload: bool = False


class TransmitterSettings(BaseModel):
    storage_dir: Path = Path(".data/files")
    database_url: str = "sqlite+aiosqlite:///./.data/files.db"


class UploadLimits(BaseModel):
    max_file_mib: int = Field(default=1024, ge=1, le=1048576)
    max_concurrent: int = Field(default=2, ge=1, le=100)
    reserve_mib: int = Field(default=512, ge=0, le=1048576)
    idle_timeout_seconds: int = Field(default=60, ge=1, le=86400)


class DesktopConfig(BaseModel):
    language: str = "en"
    auto_start: bool = False
    open_browser: bool = True


class Settings(BaseSettings):
    """Single configuration contract shared by FastAPI and the desktop UI."""

    app: AppConfig = Field(default_factory=AppConfig)
    uvicorn: UvicornConfig = Field(default_factory=UvicornConfig)
    transmitter: TransmitterSettings = Field(default_factory=TransmitterSettings)
    desktop: DesktopConfig = Field(default_factory=DesktopConfig)
    upload_limits: UploadLimits = Field(default_factory=UploadLimits)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        self.transmitter.storage_dir = resolve_storage_path(
            self.transmitter.storage_dir
        )


settings: Settings = Settings()
