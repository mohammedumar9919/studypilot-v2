"""course_units, course_subtopics, document structure links

Revision ID: 005
Revises: 004
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_units",
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
    op.create_index("idx_course_units_course_sort", "course_units", ["course_id", "sort_order"])

    op.create_table(
        "course_subtopics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "unit_id",
            sa.Uuid(),
            sa.ForeignKey("course_units.id", ondelete="CASCADE"),
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
    op.create_index("idx_course_subtopics_unit_sort", "course_subtopics", ["unit_id", "sort_order"])

    op.create_table(
        "document_unit_links",
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.Uuid(),
            sa.ForeignKey("course_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id", "unit_id"),
    )
    op.create_index("idx_document_unit_links_unit_id", "document_unit_links", ["unit_id"])

    op.create_table(
        "document_subtopic_links",
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subtopic_id",
            sa.Uuid(),
            sa.ForeignKey("course_subtopics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id", "subtopic_id"),
    )
    op.create_index("idx_document_subtopic_links_subtopic_id", "document_subtopic_links", ["subtopic_id"])


def downgrade() -> None:
    op.drop_index("idx_document_subtopic_links_subtopic_id", table_name="document_subtopic_links")
    op.drop_table("document_subtopic_links")
    op.drop_index("idx_document_unit_links_unit_id", table_name="document_unit_links")
    op.drop_table("document_unit_links")
    op.drop_index("idx_course_subtopics_unit_sort", table_name="course_subtopics")
    op.drop_table("course_subtopics")
    op.drop_index("idx_course_units_course_sort", table_name="course_units")
    op.drop_table("course_units")
