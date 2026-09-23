import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    original_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    size_bytes: Mapped[int] = mapped_column(
        nullable=False,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )
