"""exam_questions table for parsed PYQ truth layer

Revision ID: 003
Revises: 002
Create Date: 2026-06-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.String(64),
            sa.ForeignKey("courses.id"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("paper_label", sa.String(128), nullable=True),
        sa.Column("part", sa.String(8), nullable=True),
        sa.Column("question_number", sa.String(16), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("marks", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("section_title", sa.String(512), nullable=True),
        sa.Column(
            "extraction_method",
            sa.String(32),
            nullable=False,
            server_default="regex",
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_exam_questions_course_page", "exam_questions", ["course_id", "page"])
    op.create_index("idx_exam_questions_document_page", "exam_questions", ["document_id", "page"])
    op.create_index("idx_exam_questions_course_unit", "exam_questions", ["course_id", "unit"])


def downgrade() -> None:
    op.drop_index("idx_exam_questions_course_unit", table_name="exam_questions")
    op.drop_index("idx_exam_questions_document_page", table_name="exam_questions")
    op.drop_index("idx_exam_questions_course_page", table_name="exam_questions")
    op.drop_table("exam_questions")
