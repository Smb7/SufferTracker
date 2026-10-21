"""Per-user OpenCode Console connection.

Revision ID: 004_opencode_connection
Revises: 003_tailored_resume
Create Date: 2026-10-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_opencode_connection"
down_revision: Union[str, None] = "003_tailored_resume"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opencode_connections",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("api_key_ciphertext", sa.String(length=2000), nullable=False),
        sa.Column("key_hint", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=80), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("opencode_connections")
