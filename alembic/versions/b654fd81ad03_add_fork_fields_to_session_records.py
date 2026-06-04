"""add_fork_fields_to_session_records

Revision ID: b654fd81ad03
Revises: a553c0e13eff
Create Date: 2026-06-03 23:49:21.904503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b654fd81ad03'
down_revision: Union[str, Sequence[str], None] = 'a553c0e13eff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('session_records', sa.Column('parent_session_id', sa.String(), nullable=True))
    op.add_column('session_records', sa.Column('fork_message_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('session_records', 'fork_message_index')
    op.drop_column('session_records', 'parent_session_id')
