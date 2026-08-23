import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace_memberships: Mapped[list["WorkspaceMember"]] = relationship(back_populates="user")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace")
    courses: Mapped[list["Course"]] = relationship(back_populates="workspace")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member", server_default="member")

    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="workspace_memberships")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    outline_data: Mapped[dict | None] = mapped_column(JSONB)
    structure_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="corpus", server_default="corpus")
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["Workspace"] = relationship(back_populates="courses")
    study_topics: Mapped[list["StudyTopic"]] = relationship(back_populates="course")
    course_units: Mapped[list["CourseUnit"]] = relationship(back_populates="course")


class StudyTopic(Base):
    __tablename__ = "study_topics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course: Mapped["Course"] = relationship(back_populates="study_topics")
    documents: Mapped[list["Document"]] = relationship(back_populates="topic")


class CourseUnit(Base):
    __tablename__ = "course_units"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course: Mapped["Course"] = relationship(back_populates="course_units")
    parts: Mapped[list["CoursePart"]] = relationship(back_populates="unit", cascade="all, delete-orphan")
    subtopics: Mapped[list["CourseSubtopic"]] = relationship(back_populates="unit", cascade="all, delete-orphan")
    document_links: Mapped[list["DocumentUnitLink"]] = relationship(back_populates="unit", cascade="all, delete-orphan")


class CoursePart(Base):
    __tablename__ = "course_parts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_units.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    unit: Mapped["CourseUnit"] = relationship(back_populates="parts")
    subtopics: Mapped[list["CourseSubtopic"]] = relationship(back_populates="part", cascade="all, delete-orphan")
    document_links: Mapped[list["DocumentPartLink"]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
    )


class CourseSubtopic(Base):
    __tablename__ = "course_subtopics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_units.id", ondelete="CASCADE"),
        index=True,
    )
    part_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_parts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    unit: Mapped["CourseUnit"] = relationship(back_populates="subtopics")
    part: Mapped["CoursePart | None"] = relationship(back_populates="subtopics")
    document_links: Mapped[list["DocumentSubtopicLink"]] = relationship(
        back_populates="subtopic",
        cascade="all, delete-orphan",
    )


class DocumentUnitLink(Base):
    __tablename__ = "document_unit_links"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_units.id", ondelete="CASCADE"),
        primary_key=True,
    )

    document: Mapped["Document"] = relationship(back_populates="unit_links")
    unit: Mapped["CourseUnit"] = relationship(back_populates="document_links")


class DocumentSubtopicLink(Base):
    __tablename__ = "document_subtopic_links"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_subtopics.id", ondelete="CASCADE"),
        primary_key=True,
    )

    document: Mapped["Document"] = relationship(back_populates="subtopic_links")
    subtopic: Mapped["CourseSubtopic"] = relationship(back_populates="document_links")


class DocumentPartLink(Base):
    __tablename__ = "document_part_links"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    part_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_parts.id", ondelete="CASCADE"),
        primary_key=True,
    )

    document: Mapped["Document"] = relationship(back_populates="part_links")
    part: Mapped["CoursePart"] = relationship(back_populates="document_links")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_path: Mapped[str | None] = mapped_column(Text)
    extraction_quality: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("study_topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    parents: Mapped[list["ChunkParent"]] = relationship(back_populates="document")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")
    exam_questions: Mapped[list["ExamQuestion"]] = relationship(back_populates="document")
    topic: Mapped["StudyTopic | None"] = relationship(back_populates="documents")
    unit_links: Mapped[list["DocumentUnitLink"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    subtopic_links: Mapped[list["DocumentSubtopicLink"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    part_links: Mapped[list["DocumentPartLink"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    ingest_jobs: Mapped[list["IngestJob"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued")
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="full", server_default="full")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="ingest_jobs")
    workspace: Mapped["Workspace | None"] = relationship()


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id"), index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    paper_label: Mapped[str | None] = mapped_column(String(128))
    part: Mapped[str | None] = mapped_column(String(8))
    question_number: Mapped[str | None] = mapped_column(String(16))
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(16))
    section_title: Mapped[str | None] = mapped_column(String(512))
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False, default="regex")
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="exam_questions")
    concept_links: Mapped[list["ExamQuestionConcept"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class ExamConcept(Base):
    __tablename__ = "exam_concepts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[str] = mapped_column(String(64), ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_terms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    confidence: Mapped[float | None] = mapped_column(Float)
    is_unclassified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    aliases: Mapped[list["ExamConceptAlias"]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    question_links: Mapped[list["ExamQuestionConcept"]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
    )


class ExamConceptAlias(Base):
    __tablename__ = "exam_concept_aliases"

    course_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    alias: Mapped[str] = mapped_column(String(512), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_concepts.id", ondelete="CASCADE"),
        index=True,
    )

    concept: Mapped["ExamConcept"] = relationship(back_populates="aliases")


class ExamQuestionConcept(Base):
    __tablename__ = "exam_question_concepts"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")

    question: Mapped["ExamQuestion"] = relationship(back_populates="concept_links")
    concept: Mapped["ExamConcept"] = relationship(back_populates="question_links")


class ChunkParent(Base):
    __tablename__ = "chunk_parents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    document: Mapped["Document"] = relationship(back_populates="parents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="parent")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chunk_parents.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    document: Mapped["Document"] = relationship(back_populates="chunks")
    parent: Mapped["ChunkParent"] = relationship(back_populates="chunks")
    embedding: Mapped["ChunkEmbedding | None"] = relationship(back_populates="chunk")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)

    chunk: Mapped["Chunk"] = relationship(back_populates="embedding")


Index(
    "idx_documents_course_kind",
    Document.course_id,
    Document.doc_kind,
    postgresql_where=(Document.status == "ready"),
)
Index("idx_chunks_document_page", Chunk.document_id, Chunk.page)
Index("idx_exam_questions_course_page", ExamQuestion.course_id, ExamQuestion.page)
Index("idx_exam_questions_document_page", ExamQuestion.document_id, ExamQuestion.page)
Index("idx_exam_questions_course_unit", ExamQuestion.course_id, ExamQuestion.unit)
Index("idx_exam_concepts_course_id", ExamConcept.course_id)
Index(
    "idx_exam_concepts_one_unclassified_per_course",
    ExamConcept.course_id,
    unique=True,
    postgresql_where=(ExamConcept.is_unclassified.is_(True)),
)
Index("idx_exam_concept_aliases_concept_id", ExamConceptAlias.concept_id)
Index("idx_exam_question_concepts_question_id", ExamQuestionConcept.question_id)
Index("idx_exam_question_concepts_concept_id", ExamQuestionConcept.concept_id)
Index("idx_study_topics_course_sort", StudyTopic.course_id, StudyTopic.sort_order)
Index("idx_course_units_course_sort", CourseUnit.course_id, CourseUnit.sort_order)
Index("idx_course_subtopics_unit_sort", CourseSubtopic.unit_id, CourseSubtopic.sort_order)
Index("idx_course_parts_unit_sort", CoursePart.unit_id, CoursePart.sort_order)
Index("idx_course_subtopics_part_sort", CourseSubtopic.part_id, CourseSubtopic.sort_order)
Index("idx_document_unit_links_unit_id", DocumentUnitLink.unit_id)
Index("idx_document_subtopic_links_subtopic_id", DocumentSubtopicLink.subtopic_id)
Index("idx_document_part_links_part_id", DocumentPartLink.part_id)
Index("idx_courses_workspace_id", Course.workspace_id, Course.id)
Index("idx_ingest_jobs_status_created", IngestJob.status, IngestJob.created_at)
