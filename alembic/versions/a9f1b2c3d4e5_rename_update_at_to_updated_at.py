"""rename update_at to updated_at in agent_definitions

Revision ID: a9f1b2c3d4e5
Revises: d31633edbcb1
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'd31633edbcb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename update_at → updated_at, add onupdate trigger."""
    with op.batch_alter_table('agent_definitions') as batch_op:
        batch_op.alter_column(
            'update_at',
            new_column_name='updated_at',
            existing_type=sa.DateTime(),
            existing_server_default=sa.text('(CURRENT_TIMESTAMP)'),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Rename updated_at → update_at."""
    with op.batch_alter_table('agent_definitions') as batch_op:
        batch_op.alter_column(
            'updated_at',
            new_column_name='update_at',
            existing_type=sa.DateTime(),
            existing_server_default=sa.text('(CURRENT_TIMESTAMP)'),
            existing_nullable=True,
        )
