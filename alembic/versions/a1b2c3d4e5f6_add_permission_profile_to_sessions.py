"""add permission_profile to session_records

Revision ID: a1b2c3d4e5f6
Revises: 2310df6530cc
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2310df6530cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'session_records',
        sa.Column(
            'permission_profile',
            sa.String(),
            nullable=False,
            server_default='conservative',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('session_records', 'permission_profile')
