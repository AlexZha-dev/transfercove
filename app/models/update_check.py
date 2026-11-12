import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UpdateCheckRecord(Base):
    """Persistent rate-limit state for desktop release checks."""

    __tablename__ = "update_check_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_checked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
