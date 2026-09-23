from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    title: str = "WIFI TRANSMITTER"
    description: str = "Application for sharing files over a local network"
    version: str = "0.1.0"
    debug: bool = False


class UvicornConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "info"
    reload: bool = False


class TransmitterSettings(BaseModel):
    storage_dir: Path = Path(".data/files")
    database_url: str = "sqlite+aiosqlite:///./.data/files.db"


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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings: Settings = Settings()
