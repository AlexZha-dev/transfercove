import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.settings import (
    AppConfig,
    DesktopConfig,
    Settings,
    TransmitterSettings,
    UvicornConfig,
)
from app.models.base import Base


class ApplicationSettingsRecord(Base):
    __tablename__ = "application_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    app_title: Mapped[str] = mapped_column(String(255), nullable=False)
    app_description: Mapped[str] = mapped_column(String(1024), nullable=False)
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    app_debug: Mapped[bool] = mapped_column(Boolean, nullable=False)

    uvicorn_host: Mapped[str] = mapped_column(String(255), nullable=False)
    uvicorn_port: Mapped[int] = mapped_column(Integer, nullable=False)
    uvicorn_log_level: Mapped[str] = mapped_column(String(32), nullable=False)
    uvicorn_reload: Mapped[bool] = mapped_column(Boolean, nullable=False)

    storage_dir: Mapped[str] = mapped_column(String(2048), nullable=False)
    database_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    language: Mapped[str] = mapped_column(String(16), nullable=False)
    auto_start: Mapped[bool] = mapped_column(Boolean, nullable=False)
    open_browser: Mapped[bool] = mapped_column(Boolean, nullable=False)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> ApplicationSettingsRecord:
        return cls(
            id=1,
            app_title=settings.app.title,
            app_description=settings.app.description,
            app_version=settings.app.version,
            app_debug=settings.app.debug,
            uvicorn_host=settings.uvicorn.host,
            uvicorn_port=settings.uvicorn.port,
            uvicorn_log_level=settings.uvicorn.log_level,
            uvicorn_reload=settings.uvicorn.reload,
            storage_dir=str(settings.transmitter.storage_dir),
            database_url=settings.transmitter.database_url,
            language=settings.desktop.language,
            auto_start=settings.desktop.auto_start,
            open_browser=settings.desktop.open_browser,
        )

    def to_settings(self) -> Settings:
        return Settings(
            app=AppConfig(
                title=self.app_title,
                description=self.app_description,
                version=self.app_version,
                debug=self.app_debug,
            ),
            uvicorn=UvicornConfig(
                host=self.uvicorn_host,
                port=self.uvicorn_port,
                log_level=self.uvicorn_log_level,
                reload=self.uvicorn_reload,
            ),
            transmitter=TransmitterSettings(
                storage_dir=Path(self.storage_dir),
                database_url=self.database_url,
            ),
            desktop=DesktopConfig(
                language=self.language,
                auto_start=self.auto_start,
                open_browser=self.open_browser,
            ),
        )
