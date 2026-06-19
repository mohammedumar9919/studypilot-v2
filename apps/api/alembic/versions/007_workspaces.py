"""users, workspaces, workspace_members; courses.workspace_id backfill

Revision ID: 007
Revises: 006
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clerk_user_id", sa.String(128), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
    )

    op.execute(
        """
        INSERT INTO workspaces (id, name, slug)
        VALUES ('00000000-0000-4000-a000-000000000001'::uuid, 'System Demo', 'system-demo')
        """
    )

    op.add_column(
        "courses",
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        """
        UPDATE courses
        SET workspace_id = '00000000-0000-4000-a000-000000000001'::uuid
        WHERE workspace_id IS NULL
        """
    )
    op.alter_column("courses", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_courses_workspace_id",
        "courses",
        "workspaces",
        ["workspace_id"],
        ["id"],
    )
    op.create_index("idx_courses_workspace_id", "courses", ["workspace_id", "id"])


def downgrade() -> None:
    op.drop_index("idx_courses_workspace_id", table_name="courses")
    op.drop_constraint("fk_courses_workspace_id", "courses", type_="foreignkey")
    op.drop_column("courses", "workspace_id")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_table("users")
