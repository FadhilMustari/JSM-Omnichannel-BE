"""add external message id to messages

Revision ID: b2c1a9e2f9a1
Revises: 7fcf8719542a
Create Date: 2026-01-24 10:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c1a9e2f9a1"
down_revision: Union[str, None] = "7fcf8719542a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("external_message_id", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_session_external_message_id",
        "messages",
        ["session_id", "external_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_session_external_message_id",
        "messages",
        type_="unique",
    )
    op.drop_column("messages", "external_message_id")
