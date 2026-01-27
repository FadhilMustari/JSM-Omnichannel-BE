"""add ticket_links and last_read_at

Revision ID: 9a6d3c1e2f7b
Revises: e5f2c9d1b7a3
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9a6d3c1e2f7b"
down_revision = "e5f2c9d1b7a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_links",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_key", sa.String(), nullable=False),
        sa.Column(
            "session_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("ticket_key", name="uq_ticket_links_ticket_key"),
    )
    op.create_index("ix_ticket_links_session_id", "ticket_links", ["session_id"])
    op.create_index(
        "ix_ticket_links_organization_id", "ticket_links", ["organization_id"]
    )
    op.create_index("ix_ticket_links_platform", "ticket_links", ["platform"])
    op.add_column(
        "channel_sessions",
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_sessions", "last_read_at")
    op.drop_index("ix_ticket_links_platform", table_name="ticket_links")
    op.drop_index("ix_ticket_links_organization_id", table_name="ticket_links")
    op.drop_index("ix_ticket_links_session_id", table_name="ticket_links")
    op.drop_table("ticket_links")
