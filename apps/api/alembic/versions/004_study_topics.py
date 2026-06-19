"""study_topics table, documents.topic_id, courses.structure_mode

Revision ID: 004
Revises: 003
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def apply_structure_mode_backfill(connection) -> None:
    """PPL, chemistry, and outline_quality=high → mapped; all others → corpus."""
    connection.execute(
        sa.text(
            """
            UPDATE courses
            SET structure_mode = 'mapped'
            WHERE UPPER(id) = 'PPL'
               OR LOWER(id) = 'chemistry'
               OR outline_data->>'outline_quality' = 'high'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE courses
            SET structure_mode = 'corpus'
            WHERE structure_mode IS NULL
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "study_topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(64),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_study_topics_course_sort", "study_topics", ["course_id", "sort_order"])

    op.add_column(
        "courses",
        sa.Column(
            "structure_mode",
            sa.String(32),
            nullable=True,
            server_default="corpus",
        ),
    )

    apply_structure_mode_backfill(op.get_bind())

    op.alter_column("courses", "structure_mode", nullable=False, server_default="corpus")

    op.add_column(
        "documents",
        sa.Column(
            "topic_id",
            sa.Uuid(),
            sa.ForeignKey("study_topics.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_documents_topic_id", "documents", ["topic_id"])


def downgrade() -> None:
    op.drop_index("idx_documents_topic_id", table_name="documents")
    op.drop_column("documents", "topic_id")
    op.drop_column("courses", "structure_mode")
    op.drop_index("idx_study_topics_course_sort", table_name="study_topics")
    op.drop_table("study_topics")
