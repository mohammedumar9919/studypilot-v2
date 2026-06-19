"""course_parts, subtopic part_id, document_part_links

Revision ID: 006
Revises: 005
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_parts",
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
    op.create_index("idx_course_parts_unit_sort", "course_parts", ["unit_id", "sort_order"])

    op.add_column(
        "course_subtopics",
        sa.Column(
            "part_id",
            sa.Uuid(),
            sa.ForeignKey("course_parts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("idx_course_subtopics_part_sort", "course_subtopics", ["part_id", "sort_order"])

    op.create_table(
        "document_part_links",
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "part_id",
            sa.Uuid(),
            sa.ForeignKey("course_parts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id", "part_id"),
    )
    op.create_index("idx_document_part_links_part_id", "document_part_links", ["part_id"])


def downgrade() -> None:
    op.drop_index("idx_document_part_links_part_id", table_name="document_part_links")
    op.drop_table("document_part_links")
    op.drop_index("idx_course_subtopics_part_sort", table_name="course_subtopics")
    op.drop_column("course_subtopics", "part_id")
    op.drop_index("idx_course_parts_unit_sort", table_name="course_parts")
    op.drop_table("course_parts")
