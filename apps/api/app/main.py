from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.database import get_session
from app.services.course_outline import get_course_outline
from app.services.document_upload import IngestFailedError, UploadValidationError, upload_and_ingest_document
from app.services.exam.topic_frequency import compute_topic_frequency
from app.services.rag.generate import OpenRouterGenerationError, chunks_to_sources, stream_study_answer
from app.services.rag.pipeline import _build_retrieval_debug, format_sse_event, run_study_query, run_study_question

app = FastAPI(title="StudyPilot v2 API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class QueryRequest(BaseModel):
    course_id: str
    question: str = Field(min_length=1)
    preset: str = "study"
    debug: bool = False


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


@app.post("/api/v1/query", response_model=QueryResponse)
def query(body: QueryRequest, session: Session = Depends(get_session)) -> QueryResponse:
    if body.preset != "study":
        raise HTTPException(status_code=400, detail=f"Unsupported preset: {body.preset}")

    try:
        result = run_study_query(
            session,
            course_id=body.course_id,
            question=body.question,
            preset=body.preset,
            debug=body.debug,
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
def query_stream(body: QueryRequest, session: Session = Depends(get_session)) -> StreamingResponse:
    """SSE stream: retrieval_complete → token deltas → done (same final shape as POST /query)."""
    if body.preset != "study":
        raise HTTPException(status_code=400, detail=f"Unsupported preset: {body.preset}")

    try:
        retrieval = run_study_question(
            session,
            course_id=body.course_id,
            question=body.question,
            preset=body.preset,
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
    extraction_quality: dict | None = None


@app.post(
    "/api/v1/courses/{course_id}/documents",
    status_code=201,
    response_model=DocumentUploadResponse,
)
async def upload_document(
    course_id: str,
    file: UploadFile = File(...),
    doc_kind: str = Form(...),
    session: Session = Depends(get_session),
) -> DocumentUploadResponse:
    """Multipart PDF upload → synchronous ingest (v1 pilot)."""
    try:
        data = await file.read()
        result = upload_and_ingest_document(
            session,
            course_id=course_id,
            filename=file.filename or "upload.pdf",
            content_type=file.content_type,
            data=data,
            doc_kind=doc_kind,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IngestFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DocumentUploadResponse(**result)


@app.get("/api/v1/courses/{course_id}/exam/topic-frequency")
def exam_topic_frequency(course_id: str, session: Session = Depends(get_session)) -> dict:
    """Read-only PYQ topic/unit frequency (seed + keyword; no LLM)."""
    result = compute_topic_frequency(session, course_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    return {key: value for key, value in result.items() if key != "found"}


@app.get("/api/v1/courses/{course_id}/outline")
def course_outline(course_id: str, session: Session = Depends(get_session)) -> dict:
    """Read-only course TOC from outline fixture (no LLM)."""
    result = get_course_outline(session, course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Course or outline not found: {course_id}")
    return result
