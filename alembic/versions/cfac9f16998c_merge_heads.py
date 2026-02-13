"""merge heads

Revision ID: cfac9f16998c
Revises: b7c8d9e0f1a2, d1e2f3a4b5c6
Create Date: 2026-02-13 10:24:11.966320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfac9f16998c'
down_revision: Union[str, None] = ('b7c8d9e0f1a2', 'd1e2f3a4b5c6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
