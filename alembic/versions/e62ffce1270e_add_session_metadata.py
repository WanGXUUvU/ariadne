"""add session metadata

Revision ID: e62ffce1270e
Revises: f4a7c707a285
Create Date: 2026-04-28 21:51:56.705058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e62ffce1270e'
down_revision: Union[str, Sequence[str], None] = 'f4a7c707a285'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('session_records') as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.add_column(sa.Column('last_agent_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('last_skill_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('message_count', sa.Integer(), server_default=sa.text('0'), nullable=False))
        batch_op.add_column(sa.Column('last_reply_preview', sa.String(length=120), nullable=True))

    op.create_index(op.f('ix_session_records_last_agent_name'), 'session_records', ['last_agent_name'], unique=False)
    op.create_index(op.f('ix_session_records_last_skill_name'), 'session_records', ['last_skill_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_session_records_last_skill_name'), table_name='session_records')
    op.drop_index(op.f('ix_session_records_last_agent_name'), table_name='session_records')
    with op.batch_alter_table('session_records') as batch_op:
        batch_op.drop_column('last_reply_preview')
        batch_op.drop_column('message_count')
        batch_op.drop_column('last_skill_name')
        batch_op.drop_column('last_agent_name')
        batch_op.drop_column('created_at')
