"""add jira_tickets table

Revision ID: b7c8d9e0f1a2
Revises: f1a2b3c4d5e6
Create Date: 2026-02-13 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jira_tickets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_key", sa.String(), nullable=False),
        sa.Column("project_key", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("priority", sa.String(), nullable=True),
        sa.Column("assignee", sa.String(), nullable=True),
        sa.Column("reporter_email", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("ticket_key", name="uq_jira_tickets_ticket_key"),
    )
    op.create_index("ix_jira_tickets_ticket_key", "jira_tickets", ["ticket_key"])
    op.create_index("ix_jira_tickets_project_key", "jira_tickets", ["project_key"])


def downgrade() -> None:
    op.drop_index("ix_jira_tickets_project_key", table_name="jira_tickets")
    op.drop_index("ix_jira_tickets_ticket_key", table_name="jira_tickets")
    op.drop_table("jira_tickets")
