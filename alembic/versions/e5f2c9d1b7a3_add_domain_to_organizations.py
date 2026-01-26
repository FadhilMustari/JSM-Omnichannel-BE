"""add domain to organizations

Revision ID: e5f2c9d1b7a3
Revises: d4e1b7c8a9f0
Create Date: 2026-01-24 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f2c9d1b7a3"
down_revision: Union[str, None] = "d4e1b7c8a9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("domain", sa.String(), nullable=False))
    op.create_index("ix_organizations_domain", "organizations", ["domain"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organizations_domain", table_name="organizations")
    op.drop_column("organizations", "domain")
