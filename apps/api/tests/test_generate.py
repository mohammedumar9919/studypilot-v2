"""Tests for OpenRouter generation (mocked — no network)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import httpx
import pytest

from app.config import settings
from app.services.rag.generate import (
    _build_messages,
    _complete,
    generate_study_answer,
)
from app.services.rag.retrieve import RetrievedChunk


def _chunk(page: int = 11, text: str = "A lexeme is the abstract unit.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="PPL notes.pdf",
        doc_kind="notes",
        page=page,
        text=text,
        parent_text=f"Parent context for page {page}. {text}",
        rerank_score=0.82,
    )


def test_build_messages_includes_question_and_excerpts() -> None:
    chunks = [_chunk()]
    messages = _build_messages("What is a lexeme?", chunks, preset="study")
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "What is a lexeme?" in messages[1]["content"]
    assert "Question:" in messages[1]["content"]
    assert "PPL notes.pdf" in messages[1]["content"]
    assert "page 11" in messages[1]["content"]


def test_build_messages_summary_preset() -> None:
    messages = _build_messages("Lexemes", [_chunk()], preset="summary")
    assert "Summarize ONLY" in messages[0]["content"]
    assert "Topic / question:" in messages[1]["content"]


def test_build_messages_flashcards_preset() -> None:
    messages = _build_messages("Lexemes", [_chunk()], preset="flashcards")
    assert "**Q:**" in messages[0]["content"]
    assert "Focus topic:" in messages[1]["content"]


@patch("app.services.rag.generate._complete")
def test_generate_study_answer_calls_openrouter(mock_complete) -> None:
    mock_complete.return_value = "A lexeme is the abstract linguistic unit. [PPL notes.pdf p.11]"
    chunks = [_chunk(), _chunk(page=12, text="Tokens are surface forms.")]

    answer = generate_study_answer("What is a lexeme?", chunks, preset="study")

    assert answer.startswith("A lexeme")
    mock_complete.assert_called_once()
    kwargs = mock_complete.call_args.kwargs
    assert kwargs["model"] == settings.resolved_chat_model()
    assert kwargs["temperature"] == settings.llm_temperature
    assert kwargs["max_tokens"] == settings.llm_budget_tier()["max_output_tokens"]


@patch("app.services.rag.generate._complete")
def test_generate_summary_preset_uses_summary_prompt(mock_complete) -> None:
    mock_complete.return_value = "- Point one"
    generate_study_answer("Lexemes", [_chunk()], preset="summary")
    messages = mock_complete.call_args.args[0]
    assert "Summarize ONLY" in messages[0]["content"]
    assert "Topic / question:" in messages[1]["content"]


@patch("app.services.rag.generate._complete")
def test_generate_flashcards_preset_uses_flashcards_prompt(mock_complete) -> None:
    mock_complete.return_value = "**Q:** What?\n**A:** Answer."
    generate_study_answer("Lexemes", [_chunk()], preset="flashcards")
    messages = mock_complete.call_args.args[0]
    assert "**Q:**" in messages[0]["content"]
    assert "Focus topic:" in messages[1]["content"]


@patch("app.services.rag.generate._complete")
def test_generate_study_answer_respects_budget_chunk_limit(mock_complete) -> None:
    mock_complete.return_value = "Answer"
    chunks = [_chunk(page=i) for i in range(10)]

    generate_study_answer("Question?", chunks, preset="study")

    messages = mock_complete.call_args.args[0]
    user_content = messages[1]["content"]
    parent_limit = settings.llm_budget_tier()["parent_chunks"]
    assert user_content.count("--- PPL notes.pdf") == parent_limit


@patch("app.services.rag.generate._complete")
def test_generate_exam_preset_uses_exam_prompt(mock_complete) -> None:
    mock_complete.return_value = "Similar past questions on lexemes."
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename="PPL previous papers.pdf",
        doc_kind="past_paper",
        page=3,
        text="Question on lexemes.",
        parent_text="Past paper section.",
        rerank_score=0.85,
    )
    generate_study_answer("Lexemes and tokens", [chunk], preset="exam")
    messages = mock_complete.call_args.args[0]
    assert "past-exam-paper excerpts" in messages[0]["content"]
    assert "Exam question / topic:" in messages[1]["content"]


def test_generate_study_answer_rejects_unsupported_preset() -> None:
    with pytest.raises(ValueError, match="Unsupported preset"):
        generate_study_answer("Q?", [_chunk()], preset="invalid_preset")


def test_generate_study_answer_requires_chunks() -> None:
    with pytest.raises(ValueError, match="at least one chunk"):
        generate_study_answer("Q?", [], preset="study")


def test_complete_raises_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        _complete(
            [{"role": "user", "content": "hi"}],
            model="test/model",
            max_tokens=100,
            temperature=0.05,
        )


@patch("app.services.rag.generate.httpx.Client")
def test_complete_maps_openrouter_429(mock_client_cls) -> None:
    from app.services.rag.generate import OpenRouterGenerationError

    response = mock_client_cls.return_value.__enter__.return_value.post.return_value
    response.status_code = 429
    response.text = "rate limited"
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429",
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        response=response,
    )

    with pytest.raises(OpenRouterGenerationError, match="rate limit") as exc_info:
        _complete(
            [{"role": "user", "content": "hi"}],
            model="meta-llama/llama-3.3-70b-instruct:free",
            max_tokens=100,
            temperature=0.05,
        )

    assert exc_info.value.status_code == 429
