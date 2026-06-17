import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.database import get_session
from app.deps.auth import AuthContext, get_auth_context, require_course_access, require_course_access_dep, require_document_access_dep
from app.models import Course
from app.services.course_outline import get_course_outline, rebuild_course_outline, save_course_outline
from app.services.exam.topic_frequency import count_parsed_questions
from app.services.document_upload import IngestFailedError, UploadValidationError, upload_and_ingest_document
from app.services.ingest_queue import get_ingest_status
from app.services.exam.exam_status import compute_exam_status
from app.services.exam.topic_frequency import compute_topic_frequency
from app.services.course_map import (
    get_course_map_eligibility,
    promote_course_map,
    rebuild_course_map_outline,
)
from app.services.course_documents import get_course_documents, validate_source_ids
from app.services.course_structure import (
    assign_part_documents,
    assign_subtopic_documents,
    assign_unit_documents,
    confirm_course_structure,
    get_course_structure,
    import_pasted_structure,
    import_syllabus_structure,
    validate_structure_scope_ids,
    _parse_document_id_list,
)
from app.services.study_layout import get_study_layout
from app.services.workspaces import (
    CourseConflictError,
    CourseIdValidationError,
    create_workspace_course,
    get_or_create_workspace_course,
    list_workspace_courses,
    serialize_workspace_course,
)
from app.services.study_topics import (
    assign_document_topic,
    bulk_create_study_topics,
    create_study_topic,
    delete_study_topic,
    list_study_topics,
    serialize_study_topic,
    update_study_topic,
    update_structure_mode,
    validate_topic_ids,
)
from app.services.rag.generate import OpenRouterGenerationError, chunks_to_sources, stream_study_answer
from app.services.rag.pipeline import _build_retrieval_debug, format_sse_event, run_study_query, run_study_question

app = FastAPI(title="StudyPilot v2 API", version="0.1.0")


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    """Liveness + DB sanity (parsed PYQ count). Stale orphan uvicorn on :8001 shows exam_questions_ppl=0."""
    db_url = settings.database_url
    db_target = db_url.split("@", 1)[1] if "@" in db_url else db_url
    return {
        "status": "ok",
        "api_version": app.version,
        "database_target": db_target,
        "exam_questions_ppl": count_parsed_questions(session, "PPL"),
    }


class QueryRequest(BaseModel):
    course_id: str
    question: str = Field(min_length=1)
    preset: str = "study"
    debug: bool = False
    source_ids: list[str] | None = None
    topic_ids: list[str] | None = None
    unit_ids: list[str] | None = None
    part_ids: list[str] | None = None
    subtopic_ids: list[str] | None = None


class SourceResponse(BaseModel):
    document_id: str
    filename: str
    page: int
    excerpt: str


class QueryResponse(BaseModel):
    status: str
    answer: str | None = None
    sources: list[SourceResponse] = Field(default_factory=list)
    rerank_scores: list[float] = Field(default_factory=list)
    retrieval_debug: dict | None = None


def _resolve_source_ids(
    session: Session,
    *,
    course_id: str,
    source_ids: list[str] | None,
    preset: str,
) -> list[uuid.UUID] | None:
    if source_ids is None:
        return None
    return validate_source_ids(
        session,
        course_id=course_id,
        source_ids=source_ids,
        preset=preset,
    )


def _resolve_topic_ids(
    session: Session,
    *,
    course_id: str,
    topic_ids: list[str] | None,
    preset: str,
) -> list[uuid.UUID] | None:
    if topic_ids is None:
        return None
    return validate_topic_ids(
        session,
        course_id=course_id,
        topic_ids=topic_ids,
        preset=preset,
    )


def _has_structure_scope(
    *,
    unit_ids: list[str] | None,
    part_ids: list[str] | None,
    subtopic_ids: list[str] | None,
) -> bool:
    return unit_ids is not None or part_ids is not None or subtopic_ids is not None


def _resolve_retrieval_scope(
    session: Session,
    *,
    course_id: str,
    source_ids: list[str] | None,
    topic_ids: list[str] | None,
    unit_ids: list[str] | None,
    part_ids: list[str] | None,
    subtopic_ids: list[str] | None,
    preset: str,
) -> tuple[list[uuid.UUID] | None, list[uuid.UUID] | None]:
    scope_count = sum(
        [
            source_ids is not None,
            topic_ids is not None,
            _has_structure_scope(
                unit_ids=unit_ids,
                part_ids=part_ids,
                subtopic_ids=subtopic_ids,
            ),
        ]
    )
    if scope_count > 1:
        raise ValueError(
            "Only one of source_ids, topic_ids, or structure scope "
            "(unit_ids/part_ids/subtopic_ids) may be provided"
        )

    if _has_structure_scope(
        unit_ids=unit_ids,
        part_ids=part_ids,
        subtopic_ids=subtopic_ids,
    ):
        expanded = validate_structure_scope_ids(
            session,
            course_id=course_id,
            unit_ids=unit_ids,
            part_ids=part_ids,
            subtopic_ids=subtopic_ids,
            preset=preset,
        )
        return expanded, None

    resolved_source_ids = _resolve_source_ids(
        session,
        course_id=course_id,
        source_ids=source_ids,
        preset=preset,
    )
    resolved_topic_ids = _resolve_topic_ids(
        session,
        course_id=course_id,
        topic_ids=topic_ids,
        preset=preset,
    )
    return resolved_source_ids, resolved_topic_ids


@app.post("/api/v1/query", response_model=QueryResponse)
def query(
    body: QueryRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> QueryResponse:
    require_course_access(session, body.course_id, auth.workspace)
    try:
        resolved_source_ids, resolved_topic_ids = _resolve_retrieval_scope(
            session,
            course_id=body.course_id,
            source_ids=body.source_ids,
            topic_ids=body.topic_ids,
            unit_ids=body.unit_ids,
            part_ids=body.part_ids,
            subtopic_ids=body.subtopic_ids,
            preset=body.preset,
        )
        result = run_study_query(
            session,
            course_id=body.course_id,
            question=body.question,
            preset=body.preset,
            debug=body.debug,
            source_ids=resolved_source_ids,
            topic_ids=resolved_topic_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OpenRouterGenerationError as exc:
        status = exc.status_code if exc.status_code in (401, 402, 429) else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "OPENROUTER_API_KEY" in str(exc):
            raise HTTPException(
                status_code=503,
                detail="OPENROUTER_API_KEY is not set. Add it to apps/api/.env and restart the server.",
            ) from exc
        raise

    return QueryResponse(
        status=result.status,
        answer=result.answer,
        sources=[SourceResponse(**source) for source in result.sources],
        rerank_scores=result.rerank_scores,
        retrieval_debug=result.retrieval_debug,
    )


@app.post("/api/v1/query/stream")
def query_stream(
    body: QueryRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    """SSE stream: retrieval_complete → token deltas → done (same final shape as POST /query)."""
    require_course_access(session, body.course_id, auth.workspace)
    try:
        resolved_source_ids, resolved_topic_ids = _resolve_retrieval_scope(
            session,
            course_id=body.course_id,
            source_ids=body.source_ids,
            topic_ids=body.topic_ids,
            unit_ids=body.unit_ids,
            part_ids=body.part_ids,
            subtopic_ids=body.subtopic_ids,
            preset=body.preset,
        )
        retrieval = run_study_question(
            session,
            course_id=body.course_id,
            question=body.question,
            preset=body.preset,
            source_ids=resolved_source_ids,
            topic_ids=resolved_topic_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if retrieval.status != "ok":

        def refuse_stream():
            yield format_sse_event(
                "done",
                {
                    "status": "not_in_materials",
                    "answer": None,
                    "sources": [],
                    "rerank_scores": [],
                    "retrieval_debug": None,
                },
            )

        return StreamingResponse(refuse_stream(), media_type="text/event-stream")

    sources = chunks_to_sources(retrieval.chunks)
    retrieval_debug = (
        _build_retrieval_debug(retrieval.chunks, retrieval.rerank_scores) if body.debug else None
    )

    def event_stream():
        try:
            yield format_sse_event(
                "retrieval_complete",
                {
                    "sources": sources,
                    "chunk_count": len(retrieval.chunks),
                    "rerank_scores": retrieval.rerank_scores,
                    "retrieval_debug": retrieval_debug,
                },
            )
            answer_parts: list[str] = []
            for delta in stream_study_answer(body.question, retrieval.chunks, preset=body.preset):
                answer_parts.append(delta)
                yield format_sse_event("token", {"delta": delta})
            yield format_sse_event(
                "done",
                {
                    "status": "ok",
                    "answer": "".join(answer_parts),
                    "sources": sources,
                    "rerank_scores": retrieval.rerank_scores,
                    "retrieval_debug": retrieval_debug,
                },
            )
        except OpenRouterGenerationError as exc:
            status_code = exc.status_code if exc.status_code in (401, 402, 429) else 502
            yield format_sse_event("error", {"detail": str(exc), "status_code": status_code})
        except RuntimeError as exc:
            if "OPENROUTER_API_KEY" in str(exc):
                yield format_sse_event(
                    "error",
                    {
                        "detail": "OPENROUTER_API_KEY is not set. Add it to apps/api/.env and restart the server.",
                        "status_code": 503,
                    },
                )
            else:
                raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class DocumentUploadResponse(BaseModel):
    document_id: str
    course_id: str
    filename: str
    doc_kind: str
    status: str
    page_count: int | None = None
    upload_intent: str | None = None
    extraction_quality: dict | None = None
    job_id: str | None = None


class IngestStatusResponse(BaseModel):
    document_id: str
    job_id: str | None = None
    status: str
    phase: str
    progress_pct: int | None = None
    error: str | None = None
    document_status: str | None = None


class WorkspaceMeResponse(BaseModel):
    id: str
    name: str
    slug: str


class WorkspaceCourseResponse(BaseModel):
    id: str
    name: str
    structure_mode: str
    created_at: str | None = None


class CreateWorkspaceCourseRequest(BaseModel):
    id: str = Field(min_length=1, max_length=63)
    name: str | None = None


@app.get("/api/v1/workspaces/me", response_model=WorkspaceMeResponse)
def get_workspace_me(auth: AuthContext = Depends(get_auth_context)) -> WorkspaceMeResponse:
    workspace = auth.workspace
    return WorkspaceMeResponse(
        id=str(workspace.id),
        name=workspace.name,
        slug=workspace.slug,
    )


@app.get("/api/v1/workspaces/me/courses", response_model=list[WorkspaceCourseResponse])
def list_my_workspace_courses(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[WorkspaceCourseResponse]:
    courses = list_workspace_courses(session, auth.workspace.id)
    return [WorkspaceCourseResponse(**serialize_workspace_course(course)) for course in courses]


@app.post(
    "/api/v1/workspaces/me/courses",
    status_code=201,
    response_model=WorkspaceCourseResponse,
)
def create_my_workspace_course(
    body: CreateWorkspaceCourseRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> WorkspaceCourseResponse:
    try:
        course = create_workspace_course(
            session,
            auth.workspace.id,
            body.id,
            name=body.name,
        )
        session.commit()
        session.refresh(course)
    except CourseIdValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CourseConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WorkspaceCourseResponse(**serialize_workspace_course(course))


@app.post(
    "/api/v1/courses/{course_id}/documents",
    response_model=None,
    responses={
        201: {"model": DocumentUploadResponse, "description": "Synchronous ingest complete"},
        202: {"model": DocumentUploadResponse, "description": "Document queued for async ingest"},
    },
)
async def upload_document(
    course_id: str,
    file: UploadFile = File(...),
    doc_kind: str = Form(...),
    upload_intent: str | None = Form(None),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Multipart PDF upload — sync ingest (201) or async queue (202) per STUDYPILOT_INGEST_ASYNC."""
    existing = session.get(Course, course_id)
    if existing is not None:
        require_course_access(session, course_id, auth.workspace)
    else:
        try:
            get_or_create_workspace_course(session, auth.workspace.id, course_id)
            session.commit()
        except CourseIdValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except CourseConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        data = await file.read()
        result = upload_and_ingest_document(
            session,
            course_id=course_id,
            filename=file.filename or "upload.pdf",
            content_type=file.content_type,
            data=data,
            doc_kind=doc_kind,
            upload_intent=upload_intent,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IngestFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result.get("job_id"):
        return JSONResponse(status_code=202, content=result)
    return JSONResponse(status_code=201, content=result)


@app.get(
    "/api/v1/documents/{document_id}/ingest-status",
    response_model=IngestStatusResponse,
)
def document_ingest_status(
    document_id: uuid.UUID,
    session: Session = Depends(get_session),
    _document=Depends(require_document_access_dep),
) -> IngestStatusResponse:
    """Poll async ingest progress for a document."""
    status = get_ingest_status(session, document_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return IngestStatusResponse(**status)


@app.get("/api/v1/courses/{course_id}/exam/status")
def exam_status(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Read-only exam index / heatmap readiness (no LLM)."""
    result = compute_exam_status(session, course_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return {key: value for key, value in result.items() if key != "found"}


@app.get("/api/v1/courses/{course_id}/exam/topic-frequency")
def exam_topic_frequency(
    course_id: str,
    detail: str | None = None,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Read-only PYQ topic/unit frequency (seed + keyword; no LLM)."""
    include_sections = detail == "sections"
    result = compute_topic_frequency(session, course_id, include_section_detail=include_sections)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return {key: value for key, value in result.items() if key != "found"}


@app.get("/api/v1/courses/{course_id}/documents")
def course_documents(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Read-only ingested document list for Flex Study source picker (no LLM)."""
    result = get_course_documents(session, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.get("/api/v1/courses/{course_id}/study-layout")
def course_study_layout(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Read-only Flex Study sidebar mode + ingested document sources (no LLM)."""
    result = get_study_layout(session, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.get("/api/v1/courses/{course_id}/course-map-eligibility")
def course_map_eligibility(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Read-only Course Map promotion eligibility."""
    result = get_course_map_eligibility(session, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.post("/api/v1/courses/{course_id}/course-map/promote")
def course_map_promote(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Promote eligible corpus/organized course to mapped Course Map mode."""
    try:
        result = promote_course_map(session, course_id)
    except ValueError as exc:
        detail = str(exc)
        if "Course not found" in detail:
            status = 404
        else:
            status = 422
        raise HTTPException(status_code=status, detail=detail) from exc

    course = result["course"]
    layout = get_study_layout(session, course_id)
    payload: dict[str, Any] = {
        "course_id": course_id,
        "structure_mode": course.structure_mode,
        "mode": layout["mode"] if layout else "corpus",
        "promoted": result["promoted"],
    }
    if "repaired" in result:
        payload["repaired"] = result["repaired"]
    if result.get("outline_summary") is not None:
        payload["outline_summary"] = result["outline_summary"]
    return payload


@app.post("/api/v1/courses/{course_id}/course-map/rebuild-outline")
def course_map_rebuild_outline(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Re-extract syllabus TOC for stuck mapped courses (no structure_mode change)."""
    try:
        result = rebuild_course_map_outline(session, course_id)
    except ValueError as exc:
        detail = str(exc)
        if "Course not found" in detail:
            status = 404
        else:
            status = 422
        raise HTTPException(status_code=status, detail=detail) from exc

    return {
        "course_id": course_id,
        "rebuilt": result["rebuilt"],
        "outline_summary": result["outline_summary"],
    }


@app.get("/api/v1/courses/{course_id}/study-topics")
def get_study_topics(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """List user-defined study topics for organized mode."""
    topics = list_study_topics(session, course_id)
    if topics is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return {
        "course_id": course_id,
        "topics": [serialize_study_topic(topic) for topic in topics],
    }


@app.post("/api/v1/courses/{course_id}/study-topics", status_code=201)
def post_study_topic(
    course_id: str,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Create a study topic."""
    try:
        topic = create_study_topic(
            session,
            course_id,
            title=str(body.get("title", "")),
            sort_order=int(body.get("sort_order", 0)),
        )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "Course not found" in detail else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    return serialize_study_topic(topic)


@app.post("/api/v1/courses/{course_id}/study-topics/bulk", status_code=201)
def post_study_topics_bulk(
    course_id: str,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Create topic stubs in bulk; promotes corpus → organized."""
    raw_titles = body.get("titles")
    if not isinstance(raw_titles, list):
        raise HTTPException(status_code=400, detail="titles must be a list of strings")
    try:
        topics = bulk_create_study_topics(
            session,
            course_id,
            titles=[str(title) for title in raw_titles],
        )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "Course not found" in detail else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    course = session.get(Course, course_id)
    return {
        "course_id": course_id,
        "structure_mode": course.structure_mode if course else "organized",
        "topics": [serialize_study_topic(topic) for topic in topics],
    }


@app.patch("/api/v1/courses/{course_id}/structure-mode")
def patch_structure_mode(
    course_id: str,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Set structure_mode; fixture courses (PPL / YAML) cannot demote to corpus or organized."""
    try:
        course = update_structure_mode(session, course_id, str(body.get("structure_mode", "")))
    except ValueError as exc:
        detail = str(exc)
        if "Course not found" in detail:
            status = 404
        else:
            status = 400
        raise HTTPException(status_code=status, detail=detail) from exc
    layout = get_study_layout(session, course_id)
    return {
        "course_id": course_id,
        "structure_mode": course.structure_mode,
        "mode": layout["mode"] if layout else "corpus",
    }


@app.patch("/api/v1/courses/{course_id}/study-topics/{topic_id}")
def patch_study_topic(
    course_id: str,
    topic_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Update a study topic title or sort order."""
    try:
        topic = update_study_topic(
            session,
            course_id,
            topic_id,
            title=body.get("title"),
            sort_order=body.get("sort_order"),
        )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    return serialize_study_topic(topic)


@app.delete("/api/v1/courses/{course_id}/study-topics/{topic_id}", status_code=204)
def remove_study_topic(
    course_id: str,
    topic_id: uuid.UUID,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> None:
    """Delete a study topic (documents.topic_id set null via FK)."""
    try:
        delete_study_topic(session, course_id, topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/courses/{course_id}/structure")
def get_course_structure_route(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Return persisted course units/subtopics tree (SP-053a)."""
    result = get_course_structure(session, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.post("/api/v1/courses/{course_id}/structure/import-paste")
def post_structure_import_paste(
    course_id: str,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Preview pasted unit/subtopic structure without persisting."""
    try:
        result = import_pasted_structure(session, course_id, str(body.get("text", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.post("/api/v1/courses/{course_id}/structure/import-syllabus")
def post_structure_import_syllabus(
    course_id: str,
    body: dict | None = None,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Preview syllabus-derived structure without persisting."""
    payload = body or {}
    raw_document_id = payload.get("document_id")
    document_id = str(raw_document_id) if raw_document_id is not None else None
    try:
        result = import_syllabus_structure(session, course_id, document_id=document_id)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"syllabus_document_not_found", "syllabus_parse_failed"}:
            status = 422
        elif "Document not found" in detail or "Invalid document_id" in detail:
            status = 404
        else:
            status = 422
        raise HTTPException(status_code=status, detail=detail) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.post("/api/v1/courses/{course_id}/structure/confirm")
def post_structure_confirm(
    course_id: str,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Persist confirmed structure and set structure_mode=organized."""
    try:
        result = confirm_course_structure(session, course_id, body.get("units"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return result


@app.put("/api/v1/courses/{course_id}/structure/units/{unit_id}/documents")
def put_unit_documents(
    course_id: str,
    unit_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Replace document assignments for a course unit (M2M)."""
    try:
        document_ids = _parse_document_id_list(body.get("document_ids"), field_name="document_ids")
        result = assign_unit_documents(session, course_id, unit_id, document_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course unit not found: {unit_id}")
    return result


@app.put("/api/v1/courses/{course_id}/structure/parts/{part_id}/documents")
def put_part_documents(
    course_id: str,
    part_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Replace document assignments for a course part (M2M)."""
    try:
        document_ids = _parse_document_id_list(body.get("document_ids"), field_name="document_ids")
        result = assign_part_documents(session, course_id, part_id, document_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course part not found: {part_id}")
    return result


@app.put("/api/v1/courses/{course_id}/structure/subtopics/{subtopic_id}/documents")
def put_subtopic_documents(
    course_id: str,
    subtopic_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Replace document assignments for a course subtopic (M2M)."""
    try:
        document_ids = _parse_document_id_list(body.get("document_ids"), field_name="document_ids")
        result = assign_subtopic_documents(session, course_id, subtopic_id, document_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course subtopic not found: {subtopic_id}")
    return result


@app.patch("/api/v1/documents/{document_id}")
def patch_document_topic(
    document_id: uuid.UUID,
    body: dict,
    session: Session = Depends(get_session),
    _document=Depends(require_document_access_dep),
) -> dict:
    """Assign or clear study topic on a document."""
    raw_topic_id = body.get("topic_id")
    topic_id: uuid.UUID | None
    if raw_topic_id is None:
        topic_id = None
    else:
        try:
            topic_id = uuid.UUID(str(raw_topic_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid topic_id UUID: {raw_topic_id}") from exc

    try:
        document = assign_document_topic(session, document_id, topic_id=topic_id)
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc

    return {
        "document_id": str(document.id),
        "course_id": document.course_id,
        "topic_id": str(document.topic_id) if document.topic_id else None,
    }


@app.get("/api/v1/courses/{course_id}/outline")
def course_outline(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Read-only course TOC from fixture, upload, or auto-stub (no LLM)."""
    result = get_course_outline(session, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course or outline not found: {course_id}")
    return result


@app.post("/api/v1/courses/{course_id}/outline", status_code=201)
def upload_course_outline(
    course_id: str,
    body: dict,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Upload outline JSON matching DocumentOutline shape (overrides auto-stub)."""
    try:
        return save_course_outline(session, course_id, body)
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "Course not found" in detail else 400
        raise HTTPException(status_code=status, detail=detail) from exc


@app.post("/api/v1/courses/{course_id}/outline/rebuild", status_code=201)
def rebuild_course_outline_route(
    course_id: str,
    session: Session = Depends(get_session),
    _course: Course = Depends(require_course_access_dep),
) -> dict:
    """Re-extract outline from ingested notes PDFs (bookmarks or text TOC)."""
    try:
        return rebuild_course_outline(session, course_id)
    except ValueError as exc:
        detail = str(exc)
        if "Course not found" in detail:
            status = 404
        elif "Cannot rebuild" in detail or "Fixture-backed" in detail:
            status = 409
        else:
            status = 422
        raise HTTPException(status_code=status, detail=detail) from exc
