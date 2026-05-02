"""add session run trace tables

Revision ID: 9f4a8b2c1d7e
Revises: e62ffce1270e
Create Date: 2026-05-02 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4a8b2c1d7e"
down_revision: Union[str, Sequence[str], None] = "e62ffce1270e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "session_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("skill_name", sa.String(), nullable=True),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session_records.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index(op.f("ix_session_runs_agent_name"), "session_runs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_session_runs_session_id"), "session_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_session_runs_skill_name"), "session_runs", ["skill_name"], unique=False)

    op.create_table(
        "session_run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("tool_call_id", sa.String(), nullable=True),
        sa.Column("tool_result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["session_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_run_events_run_id"), "session_run_events", ["run_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_session_run_events_run_id"), table_name="session_run_events")
    op.drop_table("session_run_events")

    op.drop_index(op.f("ix_session_runs_skill_name"), table_name="session_runs")
    op.drop_index(op.f("ix_session_runs_session_id"), table_name="session_runs")
    op.drop_index(op.f("ix_session_runs_agent_name"), table_name="session_runs")
    op.drop_table("session_runs")
