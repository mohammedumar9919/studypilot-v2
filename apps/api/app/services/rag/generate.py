"""OpenRouter chat completion for study answers (generation only)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx

from app.config import settings
from app.services.rag.retrieve import RetrievedChunk

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterGenerationError(RuntimeError):
    """OpenRouter chat completion failed."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

SUPPORTED_PRESETS = frozenset({"study", "summary", "flashcards", "exam"})

_STUDY_SYSTEM_PROMPT = (
    "You are a study assistant for university course materials. "
    "Answer ONLY using the provided excerpts. "
    "If the excerpts do not contain enough information, say so briefly. "
    "Cite sources inline as [filename p.N]. Be concise and accurate."
)

_SUMMARY_SYSTEM_PROMPT = (
    "You are a study assistant for university course materials. "
    "Summarize ONLY using the provided excerpts. "
    "Output concise bullet points (markdown `-` bullets). "
    "Focus on the topic in the student's question. "
    "Cite sources inline as [filename p.N]. "
    "If the excerpts do not contain enough information, say so briefly."
)

_FLASHCARDS_SYSTEM_PROMPT = (
    "You are a study assistant for university course materials. "
    "Create flashcards ONLY from the provided excerpts. "
    "Output 3–8 question/answer pairs in markdown using this format:\n"
    "**Q:** ...\n**A:** ...\n"
    "Include [filename p.N] on answers where relevant. "
    "If the excerpts do not contain enough material, say so briefly."
)

_EXAM_SYSTEM_PROMPT = (
    "You are an exam preparation assistant. "
    "Answer ONLY using the provided past-exam-paper excerpts. "
    "Do not invent questions or answers not supported by the excerpts. "
    "When visible, identify the question style (short answer, essay, numerical, etc.). "
    "Surface similar past questions from the excerpts when relevant to the student's topic. "
    "You may suggest brief pointers on what to review in course notes, but do not invent note content. "
    "Cite sources inline as [filename p.N]. "
    "If the excerpts are insufficient, say so and suggest uploading or indexing past exam papers."
)

_SYSTEM_PROMPTS: dict[str, str] = {
    "study": _STUDY_SYSTEM_PROMPT,
    "summary": _SUMMARY_SYSTEM_PROMPT,
    "flashcards": _FLASHCARDS_SYSTEM_PROMPT,
    "exam": _EXAM_SYSTEM_PROMPT,
}

_USER_PROMPT_LABELS: dict[str, str] = {
    "study": "Question",
    "summary": "Topic / question",
    "flashcards": "Focus topic",
    "exam": "Exam question / topic",
}


def validate_preset(preset: str) -> None:
    if preset not in SUPPORTED_PRESETS:
        raise ValueError(f"Unsupported preset: {preset}")


def _excerpt_text(chunk: RetrievedChunk, *, max_chars: int = 400) -> str:
    body = chunk.parent_text or chunk.text
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 1].rstrip() + "…"


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        parts.append(
            f"--- {chunk.filename} (page {chunk.page}) ---\n"
            f"{chunk.parent_text or chunk.text}"
        )
    return "\n\n".join(parts)


def _build_messages(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    preset: str = "study",
) -> list[dict[str, str]]:
    validate_preset(preset)
    label = _USER_PROMPT_LABELS[preset]
    return [
        {"role": "system", "content": _SYSTEM_PROMPTS[preset]},
        {
            "role": "user",
            "content": f"Excerpts:\n\n{_build_context_block(chunks)}\n\n{label}: {question}",
        },
    ]


def _prepare_generation(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    preset: str,
) -> tuple[list[dict[str, str]], str, int, float]:
    validate_preset(preset)
    if not chunks:
        raise ValueError("generation requires at least one chunk")

    tier = settings.llm_budget_tier()
    limited = chunks[: tier["parent_chunks"]]
    messages = _build_messages(question, limited, preset=preset)
    return (
        messages,
        settings.resolved_chat_model(),
        tier["max_output_tokens"],
        settings.llm_temperature,
    )


def _complete(
    messages: list[dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call OpenRouter chat completions. Patch this in tests — no network in CI."""
    api_key = settings.openrouter_api_key
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://studypilot.local",
        "X-Title": "StudyPilot v2",
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(OPENROUTER_CHAT_URL, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500]
            if response.status_code == 429:
                raise OpenRouterGenerationError(
                    "OpenRouter rate limit hit (429). Free models allow ~20 req/min and "
                    "50 req/day without credits. Wait a minute, add credits at openrouter.ai, "
                    "or set OPENROUTER_DEV_CHAT_MODEL=deepseek/deepseek-chat in .env.",
                    status_code=429,
                ) from exc
            raise OpenRouterGenerationError(
                f"OpenRouter request failed ({response.status_code}): {detail}",
                status_code=response.status_code,
            ) from exc
        data = response.json()

    usage = data.get("usage") or {}
    logger.info(
        "openrouter completion model=%s prompt_tokens=%s completion_tokens=%s",
        model,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
    )

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("OpenRouter returned empty content")
    return str(content).strip()


def _stream_complete(
    messages: list[dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    temperature: float,
) -> Iterator[str]:
    """Stream OpenRouter chat completion token deltas. Patch in tests — no network in CI."""
    api_key = settings.openrouter_api_key
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://studypilot.local",
        "X-Title": "StudyPilot v2",
    }

    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", OPENROUTER_CHAT_URL, json=payload, headers=headers) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.read().decode("utf-8", errors="replace")[:500]
                if response.status_code == 429:
                    raise OpenRouterGenerationError(
                        "OpenRouter rate limit hit (429). Free models allow ~20 req/min and "
                        "50 req/day without credits. Wait a minute, add credits at openrouter.ai, "
                        "or set OPENROUTER_DEV_CHAT_MODEL=deepseek/deepseek-chat in .env.",
                        status_code=429,
                    ) from exc
                raise OpenRouterGenerationError(
                    f"OpenRouter request failed ({response.status_code}): {detail}",
                    status_code=response.status_code,
                ) from exc

            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                chunk = json.loads(data_str)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield str(content)


def chunks_to_sources(chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": str(chunk.document_id),
            "filename": chunk.filename,
            "page": chunk.page,
            "excerpt": _excerpt_text(chunk),
        }
        for chunk in chunks
    ]


def generate_study_answer(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    preset: str = "study",
) -> str:
    """Generate grounded output from retrieved chunks (study, summary, or flashcards)."""
    messages, model, max_tokens, temperature = _prepare_generation(
        question, chunks, preset=preset
    )
    return _complete(
        messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def stream_study_answer(
    question: str,
    chunks: list[RetrievedChunk],
    *,
    preset: str = "study",
) -> Iterator[str]:
    """Stream grounded output token deltas (study, summary, or flashcards)."""
    messages, model, max_tokens, temperature = _prepare_generation(
        question, chunks, preset=preset
    )
    yield from _stream_complete(
        messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
