"""LangSmith tracing and evaluation helpers for the multimodal RAG app."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()


def langsmith_enabled() -> bool:
    return bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))


def score_request(
    request_type: str,
    query: str,
    answer: str,
    *,
    results: list[Dict[str, Any]] | None = None,
    latency_seconds: float = 0.0,
    success: bool = True,
    error: str | None = None,
) -> Dict[str, Any]:
    """Create a lightweight quality and reliability score for a user request."""
    normalized_query = str(query or "").strip()
    normalized_answer = str(answer or "").strip()
    result_count = len(results or [])
    query_score = min(15, 15 if len(normalized_query.split()) >= 3 else len(normalized_query.split()) * 5)
    answer_score = 35 if normalized_answer else 0
    evidence_score = min(35, result_count * 12) if request_type == "search" else (35 if normalized_answer else 0)
    latency_score = max(0, min(15, round(15 * (1 - max(latency_seconds - 2, 0) / 28), 1)))
    if not success:
        latency_score = 0

    score = round(query_score + answer_score + evidence_score + latency_score)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_type": request_type,
        "query": normalized_query[:240],
        "score": score,
        "latency_seconds": round(max(latency_seconds, 0), 2),
        "success": success,
        "result_count": result_count,
        "answer_length": len(normalized_answer),
        "error": str(error)[:240] if error else None,
        "dimensions": {
            "query_quality": query_score,
            "answer_present": answer_score,
            "evidence": evidence_score,
            "latency": latency_score,
        },
    }


def record_request(history: list[Dict[str, Any]], event: Dict[str, Any], limit: int = 100) -> None:
    """Keep the latest request events in Streamlit session state."""
    history.append(event)
    del history[:-limit]


def summarize_requests(history: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Return aggregate metrics for the observability view."""
    if not history:
        return {"count": 0, "success_rate": 0.0, "average_score": 0.0, "average_latency": 0.0}
    successful = [event for event in history if event.get("success")]
    return {
        "count": len(history),
        "success_rate": round(len(successful) / len(history) * 100, 1),
        "average_score": round(sum(event.get("score", 0) for event in history) / len(history), 1),
        "average_latency": round(sum(event.get("latency_seconds", 0) for event in history) / len(history), 2),
    }


try:
    from langsmith import traceable
except Exception:  # pragma: no cover - optional monitoring dependency
    def traceable(*args: Any, **kwargs: Any):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(function):
            return function

        return decorator


def answer_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Score answer overlap with the reference answer in a dataset example."""
    outputs = getattr(example, "outputs", None) or {}
    expected = str(outputs.get("answer", "")).strip().lower()
    actual = str((run.outputs or {}).get("answer", "")).strip().lower()
    if not expected:
        return {"key": "has_answer", "score": bool(actual), "comment": "No reference answer supplied."}

    expected_terms = {term for term in expected.split() if len(term) > 3}
    overlap = len(expected_terms.intersection(actual.split())) / max(len(expected_terms), 1)
    return {
        "key": "answer_reference_overlap",
        "score": overlap,
        "comment": f"Matched {overlap:.0%} of reference terms.",
    }


def groundedness_evaluator(run: Any, example: Any) -> Dict[str, Any]:
    """Check that the evaluated answer includes retrieved context."""
    outputs = run.outputs or {}
    answer = str(outputs.get("answer", "")).strip()
    context = str(outputs.get("context", "")).strip()
    score = bool(answer) and bool(context)
    return {
        "key": "groundedness_presence",
        "score": score,
        "comment": "Answer and retrieved context are present." if score else "Missing answer or context.",
    }


def evaluate_dataset(dataset: str, *, max_concurrency: int = 2):
    """Evaluate the traced RAG target against a LangSmith dataset."""
    if not langsmith_enabled():
        raise RuntimeError("Set LANGSMITH_API_KEY before running an evaluation.")

    from langsmith import Client
    from pipeline import rag_query_with_context

    def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = str(inputs.get("query", "")).strip()
        answer, context = rag_query_with_context(query)
        return {"answer": answer, "context": context}

    return Client().evaluate(
        target,
        data=dataset,
        evaluators=[answer_evaluator, groundedness_evaluator],
        experiment_prefix=os.getenv("LANGSMITH_EXPERIMENT", "multimodal-rag"),
        max_concurrency=max_concurrency,
    )


__all__ = [
    "answer_evaluator",
    "evaluate_dataset",
    "groundedness_evaluator",
    "langsmith_enabled",
    "traceable",
]