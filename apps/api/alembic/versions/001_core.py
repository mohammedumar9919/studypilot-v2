"""core schema

Revision ID: 001
Revises:
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "courses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.String(64), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("doc_kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("page_count", sa.Integer()),
        sa.Column("file_path", sa.Text()),
        sa.Column("extraction_quality", sa.dialects.postgresql.JSONB()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_course_id", "documents", ["course_id"])

    op.create_table(
        "chunk_parents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("chunk_parents.id", ondelete="CASCADE")),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
    )
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN text_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
        """
    )
    op.create_index("idx_chunks_document_page", "chunks", ["document_id", "page"])
    op.create_index("idx_chunks_tsv", "chunks", ["text_tsv"], postgresql_using="gin")

    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
    )
    op.execute(
        """
        CREATE INDEX idx_embeddings_hnsw ON chunk_embeddings
        USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_documents_course_kind ON documents (course_id, doc_kind)
        WHERE status = 'ready'
        """
    )


def downgrade() -> None:
    op.drop_index("idx_documents_course_kind", table_name="documents")
    op.drop_index("idx_embeddings_hnsw", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    op.drop_index("idx_chunks_tsv", table_name="chunks")
    op.drop_index("idx_chunks_document_page", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("chunk_parents")
    op.drop_index("ix_documents_course_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("courses")
