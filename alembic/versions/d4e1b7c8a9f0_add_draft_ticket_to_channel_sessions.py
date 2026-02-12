"""add draft ticket to channel sessions

Revision ID: d4e1b7c8a9f0
Revises: c3d2f1b0a6c4
Create Date: 2026-01-24 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e1b7c8a9f0"
down_revision = "b2c1a9e2f9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channel_sessions",
        sa.Column("draft_ticket", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_sessions", "draft_ticket")
