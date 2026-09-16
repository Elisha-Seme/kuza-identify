"""LLM Scoring Service (Section 3.3 / Section 4).

Scores a single child-authored response into one domain score (0-100) plus
evidence text, in English or Kiswahili, from short and often messy text. Stateless
and horizontally scalable — one call per response.

CONSTRAINT (Section 3.6): this service produces evidence only. It returns a
per-domain score and evidence; it NEVER writes a decision. Decisions live solely
on PanelReview. Writing to the DB is done by the Aggregation Engine, not here.

When ANTHROPIC_API_KEY is unset it falls back to a deterministic local scorer so
the whole pipeline runs end-to-end without credentials. The real Claude path is
used automatically whenever the key is present.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.enums import Language

_SYSTEM = (
    "You are a scorer for a gifted-learner identification screener used in "
    "Kenyan informal-settlement schools. You score ONE open-ended, child-authored "
    "answer for reasoning depth and error-pattern type. Answers may be in English "
    "or Kiswahili and are often short or messy — reward correct method and "
    "reasoning process over neat presentation or perfect arithmetic. You NEVER "
    "make an advancement decision; you only score and give evidence. "
    "Respond with STRICT JSON only: "
    '{"score": <integer 0-100>, "evidence": "<one or two sentences on the '
    'reasoning shown and any error pattern>"}.'
)


@dataclass(frozen=True)
class ScoreResult:
    score: int
    evidence_text: str
    scoring_model_version: str


def _model_version() -> str:
    s = get_settings()
    return f"{s.scoring_model}+{s.scoring_prompt_version}"


def _deterministic_fallback(domain: str, raw_response: str) -> ScoreResult:
    """Stable pseudo-score so the pipeline runs without an API key.

    Deterministic in the response text so seed data and tests are reproducible.
    Clearly marked in the version string so nobody mistakes it for a real score.
    """
    digest = hashlib.sha256(f"{domain}:{raw_response}".encode()).hexdigest()
    base = int(digest[:4], 16) % 101  # 0-100
    # Longer, more articulated answers nudge slightly higher — a crude proxy only.
    length_bonus = min(len(raw_response.split()), 20)
    score = max(0, min(100, base // 2 + length_bonus))
    return ScoreResult(
        score=score,
        evidence_text=(
            "[Demo scorer, no ANTHROPIC_API_KEY set] Deterministic placeholder "
            f"score for domain '{domain}'. Set the API key for real scoring."
        ),
        scoring_model_version=f"mock+{get_settings().scoring_prompt_version}",
    )


def score_response(
    *,
    domain: str,
    item_prompt: str,
    expected_reasoning: str,
    raw_response: str,
    language: Language,
) -> ScoreResult:
    settings = get_settings()
    if not settings.llm_enabled:
        return _deterministic_fallback(domain, raw_response)

    # Imported lazily so the package imports fine without the SDK/key in dev.
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_content = (
        f"Domain: {domain}\n"
        f"Language of answer: {language.value}\n"
        f"Item shown to the child:\n{item_prompt}\n\n"
        f"Scoring guidance (never shown to the child):\n{expected_reasoning}\n\n"
        f"Child's answer:\n{raw_response}\n\n"
        "Return the strict JSON described in the system prompt."
    )
    message = client.messages.create(
        model=settings.scoring_model,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    text = next((b.text for b in message.content if b.type == "text"), "").strip()
    score, evidence = _parse_scoring_json(text)
    return ScoreResult(
        score=score,
        evidence_text=evidence,
        scoring_model_version=_model_version(),
    )


def _parse_scoring_json(text: str) -> tuple[int, str]:
    """Parse the model's JSON, tolerating a stray code fence."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        data = json.loads(cleaned)
        score = int(data["score"])
        evidence = str(data["evidence"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        # Never crash the pipeline on a malformed response — record it as evidence.
        return 0, f"[scoring parse error] raw model output: {text[:400]}"
    return max(0, min(100, score)), evidence
