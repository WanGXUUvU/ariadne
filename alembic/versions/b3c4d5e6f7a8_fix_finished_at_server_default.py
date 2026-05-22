"""fix finished_at nullable and server_default on session_runs

Revision ID: b3c4d5e6f7a8
Revises: 2cadfe282993
Create Date: 2026-05-21 00:00:00.000000

问题根因：
  原始迁移创建 finished_at 时是 NOT NULL + server_default=CURRENT_TIMESTAMP，
  但 Python 模型后来改成 nullable=True 且没有 server_default。
  SQLAlchemy 看到没有 server_default，在 INSERT 时会显式传 NULL，
  触发 DB 层的 NOT NULL 约束。

此迁移将列修正为 NOT NULL + server_default=CURRENT_TIMESTAMP，
与 DB 真实状态对齐，并让 Python 模型的 server_default 生效。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = '2cadfe282993'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite 不支持 ALTER COLUMN，需要用 batch_alter_table 重建列定义
    with op.batch_alter_table('session_runs', schema=None) as batch_op:
        batch_op.alter_column(
            'finished_at',
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        )


def downgrade() -> None:
    with op.batch_alter_table('session_runs', schema=None) as batch_op:
        batch_op.alter_column(
            'finished_at',
            existing_type=sa.DateTime(),
            nullable=True,
            server_default=None,
        )
