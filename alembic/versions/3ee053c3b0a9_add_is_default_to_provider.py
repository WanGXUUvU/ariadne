"""add_is_default_to_provider

Revision ID: 3ee053c3b0a9
Revises: 1631ce689f66
Create Date: 2026-05-22 09:58:30.916388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ee053c3b0a9'
down_revision: Union[str, Sequence[str], None] = '1631ce689f66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('provider_configs', sa.Column('is_default', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('provider_configs', 'is_default')
