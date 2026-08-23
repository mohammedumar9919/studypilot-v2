"""exam_concepts schema for ingest-time concept extraction (SP-060a)

Revision ID: 009
Revises: 008
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_concepts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(64),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column(
            "canonical_terms",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "is_unclassified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_exam_concepts_course_id", "exam_concepts", ["course_id"])
    op.create_index(
        "idx_exam_concepts_one_unclassified_per_course",
        "exam_concepts",
        ["course_id"],
        unique=True,
        postgresql_where=sa.text("is_unclassified = true"),
    )

    op.create_table(
        "exam_concept_aliases",
        sa.Column(
            "course_id",
            sa.String(64),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("alias", sa.String(512), primary_key=True),
        sa.Column(
            "concept_id",
            sa.Uuid(),
            sa.ForeignKey("exam_concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_exam_concept_aliases_concept_id",
        "exam_concept_aliases",
        ["concept_id"],
    )

    op.create_table(
        "exam_question_concepts",
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("exam_questions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "concept_id",
            sa.Uuid(),
            sa.ForeignKey("exam_concepts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "weight",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
    )
    op.create_index(
        "idx_exam_question_concepts_question_id",
        "exam_question_concepts",
        ["question_id"],
    )
    op.create_index(
        "idx_exam_question_concepts_concept_id",
        "exam_question_concepts",
        ["concept_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_exam_question_concepts_concept_id", table_name="exam_question_concepts")
    op.drop_index("idx_exam_question_concepts_question_id", table_name="exam_question_concepts")
    op.drop_table("exam_question_concepts")
    op.drop_index("idx_exam_concept_aliases_concept_id", table_name="exam_concept_aliases")
    op.drop_table("exam_concept_aliases")
    op.drop_index("idx_exam_concepts_one_unclassified_per_course", table_name="exam_concepts")
    op.drop_index("idx_exam_concepts_course_id", table_name="exam_concepts")
    op.drop_table("exam_concepts")
