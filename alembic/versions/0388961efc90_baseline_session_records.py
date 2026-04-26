"""baseline session_records

Revision ID: 0388961efc90
Revises: 
Create Date: 2026-04-26 18:56:54.168014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0388961efc90'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "session_records",  # 表名
        sa.Column("session_id", sa.String(), primary_key=True, nullable=False),  # 主键
        sa.Column("state_json", sa.Text(), nullable=False),  # 状态JSON
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),  # 更新时间
    )
    op.create_index(
        "ix_session_records_session_id",  # 索引名
        "session_records",  # 表名
        ["session_id"],  # 索引字段
        unique=False,  # 普通索引
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_session_records_session_id", table_name="session_records")  # 先删索引
    op.drop_table("session_records")  # 再删表

