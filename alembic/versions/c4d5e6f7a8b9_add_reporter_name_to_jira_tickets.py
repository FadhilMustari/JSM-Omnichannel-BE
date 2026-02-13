"""add reporter_name to jira_tickets

Revision ID: c4d5e6f7a8b9
Revises: b7c8d9e0f1a2
Create Date: 2026-02-13 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jira_tickets", sa.Column("reporter_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jira_tickets", "reporter_name")
