"""update jsm org user schema

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-02-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("jsm_id", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("jsm_uuid", sa.String(), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column("users", sa.Column("jsm_account_id", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_authenticated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_unique_constraint("uq_organizations_jsm_id", "organizations", ["jsm_id"])
    op.create_unique_constraint("uq_users_jsm_account_id", "users", ["jsm_account_id"])

    op.execute('DROP INDEX IF EXISTS ix_organizations_domain')
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'organizations_domain_key'
            ) THEN
                ALTER TABLE organizations DROP CONSTRAINT organizations_domain_key;
            END IF;
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'organizations_name_key'
            ) THEN
                ALTER TABLE organizations DROP CONSTRAINT organizations_name_key;
            END IF;
        END $$;
        """
    )
    op.drop_column("organizations", "domain")

    op.drop_column("users", "name")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("name", sa.String(), nullable=False, server_default=""),
    )

    op.add_column(
        "organizations",
        sa.Column("domain", sa.String(), nullable=False, server_default=""),
    )

    op.create_index("ix_organizations_domain", "organizations", ["domain"], unique=False)
    op.create_unique_constraint("organizations_domain_key", "organizations", ["domain"])
    op.create_unique_constraint("organizations_name_key", "organizations", ["name"])

    op.drop_constraint("uq_users_jsm_account_id", "users", type_="unique")
    op.drop_constraint("uq_organizations_jsm_id", "organizations", type_="unique")

    op.drop_column("users", "is_authenticated")
    op.drop_column("users", "jsm_account_id")
    op.drop_column("organizations", "updated_at")
    op.drop_column("organizations", "is_active")
    op.drop_column("organizations", "jsm_uuid")
    op.drop_column("organizations", "jsm_id")
