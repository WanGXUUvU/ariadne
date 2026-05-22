"""add tool_call_id saved_messages event_index to pending_approvals

Revision ID: 2cadfe282993
Revises: 860cee3628fc
Create Date: 2026-05-20 22:16:12.388497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2cadfe282993'
down_revision: Union[str, Sequence[str], None] = '860cee3628fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 只加三列，其余 alter_column / create_foreign_key SQLite 不支持，跳过
    op.add_column('pending_approvals', sa.Column('tool_call_id', sa.String(), nullable=True))
    op.add_column('pending_approvals', sa.Column('saved_messages', sa.JSON(), nullable=True))
    op.add_column('pending_approvals', sa.Column('event_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pending_approvals', 'event_index')
    op.drop_column('pending_approvals', 'saved_messages')
    op.drop_column('pending_approvals', 'tool_call_id')
