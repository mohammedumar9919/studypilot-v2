"""ingest_jobs queue table for async ingest (SP-013a)

Revision ID: 008
Revises: 007
Create Date: 2026-06-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("phase", sa.String(32), nullable=False, server_default="full"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ingest_jobs_document_id", "ingest_jobs", ["document_id"])
    op.create_index("ix_ingest_jobs_status_created", "ingest_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ingest_jobs_status_created", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_document_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
