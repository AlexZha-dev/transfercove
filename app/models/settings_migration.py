from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LAN_ADDRESS_MIGRATION_ID = 1


class SettingsMigration(Base):
    __tablename__ = "desktop_settings_migrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
