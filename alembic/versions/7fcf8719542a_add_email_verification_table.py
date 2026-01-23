"""add email verification table

Revision ID: 7fcf8719542a
Revises: a0ec2ef83d5a
Create Date: 2026-01-23 21:17:49.140834

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7fcf8719542a'
down_revision: Union[str, None] = 'a0ec2ef83d5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_email_verifications_token",
        "email_verifications",
        ["token"],
        unique=True,
    )

    op.create_index(
        "ix_email_verifications_session_id",
        "email_verifications",
        ["session_id"],
    )


def downgrade():
    op.drop_index("ix_email_verifications_token", table_name="email_verifications")
    op.drop_index("ix_email_verifications_session_id", table_name="email_verifications")
    op.drop_table("email_verifications")
