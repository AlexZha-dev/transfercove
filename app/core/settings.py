from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    title: str = "WIFI TRANSMITTER"
    description: str = "Application for shere files in server using local network"
    version: str = "0.0"
    debug: bool = False


class UvicornConfig(BaseModel):
    host: str = "localhost"
    port: int = 8000
    log_level: str | int = "info"
    reload: bool = False


class TransmitterSettings(BaseModel):
    pass


class Settings(BaseSettings):
    app: AppConfig = AppConfig()
    uvicorn: UvicornConfig = UvicornConfig()
    transmitter: TransmitterSettings = TransmitterSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings: Settings = Settings()
