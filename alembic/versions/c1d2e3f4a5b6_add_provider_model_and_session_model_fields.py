"""add provider_configs, model_settings, and model fields to session_records

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f6", "b3c4d5e6f7a8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建 provider_configs 表
    op.create_table(
        "provider_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("base_url", sa.String, nullable=False),
        sa.Column("api_key", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # 2. 创建 model_settings 表
    op.create_table(
        "model_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("provider_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("model_id", sa.String, nullable=False),
        sa.Column("display_name", sa.String, nullable=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("supports_thinking", sa.Integer, nullable=False, server_default="0"),
        sa.Column("thinking_style", sa.String, nullable=True),
        sa.Column("effort_levels", sa.Text, nullable=True),
        sa.Column("context_length", sa.Integer, nullable=True),
        sa.Column("supports_tools", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_id", "model_id"),
    )

    # 3. session_records 新增模型选择字段
    with op.batch_alter_table("session_records") as batch_op:
        batch_op.add_column(sa.Column("model_provider_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("model_id", sa.String, nullable=True))
        batch_op.add_column(sa.Column("thinking_enabled", sa.Integer, nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("thinking_effort", sa.String, nullable=False, server_default="medium"))


def downgrade() -> None:
    # 回滚顺序与 upgrade 相反
    with op.batch_alter_table("session_records") as batch_op:
        batch_op.drop_column("thinking_effort")
        batch_op.drop_column("thinking_enabled")
        batch_op.drop_column("model_id")
        batch_op.drop_column("model_provider_id")

    op.drop_table("model_settings")
    op.drop_table("provider_configs")
