"""repair databases created without the files table

Revision ID: e5f0c48f0c1d
Revises: d0b65365c266
Create Date: 2026-09-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "e5f0c48f0c1d"
down_revision: Union[str, Sequence[str], None] = "d0b65365c266"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the files table when an older build skipped its migration."""

    if inspect(op.get_bind()).has_table("files"):
        return

    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_name"),
    )


def downgrade() -> None:
    """Keep the repaired table when rolling back the marker migration."""
