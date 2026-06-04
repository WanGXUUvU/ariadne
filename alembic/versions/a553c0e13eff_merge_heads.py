"""merge_heads

Revision ID: a553c0e13eff
Revises: a9f1b2c3d4e5, c7b1f2e4a9d3
Create Date: 2026-06-03 23:48:30.376593

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a553c0e13eff'
down_revision: Union[str, Sequence[str], None] = ('a9f1b2c3d4e5', 'c7b1f2e4a9d3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
