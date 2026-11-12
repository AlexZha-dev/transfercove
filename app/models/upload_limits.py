from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.settings import UploadLimits
from app.models.base import Base


class UploadLimitsRecord(Base):
    __tablename__ = "upload_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    max_file_mib: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False)
    reserve_mib: Mapped[int] = mapped_column(Integer, nullable=False)
    idle_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    @classmethod
    def from_limits(cls, limits: UploadLimits) -> "UploadLimitsRecord":
        return cls(id=1, **limits.model_dump())

    def to_limits(self) -> UploadLimits:
        return UploadLimits.model_validate(self, from_attributes=True)
