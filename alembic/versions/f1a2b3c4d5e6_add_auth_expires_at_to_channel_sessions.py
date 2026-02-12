"""add auth_expires_at to channel_sessions

Revision ID: f1a2b3c4d5e6
Revises: 9a6d3c1e2f7b
Create Date: 2026-02-12 10:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "9a6d3c1e2f7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channel_sessions",
        sa.Column("auth_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_sessions", "auth_expires_at")
