"""add outbox messages table

Revision ID: c3d2f1b0a6c4
Revises: b2c1a9e2f9a1
Create Date: 2026-01-24 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d2f1b0a6c4"
down_revision: Union[str, None] = "b2c1a9e2f9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_sessions.id"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("external_user_id", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_messages_session_id",
        "outbox_messages",
        ["session_id"],
    )
    op.create_index(
        "ix_outbox_messages_status",
        "outbox_messages",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_messages_status", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_session_id", table_name="outbox_messages")
    op.drop_table("outbox_messages")
