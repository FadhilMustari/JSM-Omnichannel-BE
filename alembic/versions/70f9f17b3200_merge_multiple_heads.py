"""merge multiple heads

Revision ID: 70f9f17b3200
Revises: c4d5e6f7a8b9, cfac9f16998c
Create Date: 2026-02-13 11:12:00.649183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70f9f17b3200'
down_revision: Union[str, None] = ('c4d5e6f7a8b9', 'cfac9f16998c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
