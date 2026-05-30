"""add batch_id to pending_approvals

Revision ID: c7b1f2e4a9d3
Revises: b3c4d5e6f7a8
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7b1f2e4a9d3'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('pending_approvals') as batch_op:
        batch_op.add_column(sa.Column('batch_id', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_pending_approvals_batch_id'), ['batch_id'], unique=False)

    op.execute("UPDATE pending_approvals SET batch_id = run_id WHERE batch_id IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('pending_approvals') as batch_op:
        batch_op.drop_index(batch_op.f('ix_pending_approvals_batch_id'))
        batch_op.drop_column('batch_id')
