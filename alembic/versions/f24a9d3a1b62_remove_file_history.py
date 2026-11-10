"""Remove the obsolete file history table.

Revision ID: f24a9d3a1b62
Revises: e5f0c48f0c1d
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "f24a9d3a1b62"
down_revision = "e5f0c48f0c1d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if inspect(op.get_bind()).has_table("files"):
        op.drop_table("files")


def downgrade() -> None:
    # The schema can be restored for older versions, but deleted history cannot.
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
