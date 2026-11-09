"""Document classification.

A deterministic scorer runs first.  When it is not confident, and a language
model is configured, the model is asked to choose from the same closed
vocabulary; a disagreement lowers confidence rather than silently overriding
the rules.  Anything still uncertain is marked for manual review.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .knowledge import doc_label, doc_types

#: Below this the document is flagged "Unknown Document Type - Manual Review Required".
CONFIDENT_THRESHOLD = 0.55
#: Below this we ask the language model for a second opinion (when available).
LLM_ASSIST_THRESHOLD = 0.75

STRONG_WEIGHT = 4.0
KEYWORD_WEIGHT = 1.0
NEGATIVE_WEIGHT = -4.0
TITLE_BONUS = 2.5
FILENAME_WEIGHT = 1.5


@dataclass
class Classification:
    doc_type: str
    confidence: float
    method: str
    rationale: str
    scores: Dict[str, float] = field(default_factory=dict)
    needs_manual_review: bool = False


#: Characters kept when normalising for comparison. The Kannada block
#: (U+0C80-U+0CFF) is preserved: stripping it would make every Kannada
#: document score zero against the vocabulary.
_KEEP_RE = re.compile("[^a-z0-9/().,\\-\u0C80-\u0CFF ]+")

def _normalise(text: str) -> str:
    from .extraction.base import sanitise_text

    text = sanitise_text(text).lower()
    text = text.replace("\u00a0", " ")
    text = _KEEP_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text)


def _count_phrase(haystack: str, phrase: str) -> int:
    phrase = phrase.lower().strip()
    if not phrase:
        return 0
    return haystack.count(phrase)


def score_types(text: str, filename: str = "") -> Dict[str, float]:
    """Score every known document type against the text and the filename."""
    body = _normalise(text or "")
    head = body[:4000]          # the opening of a deed usually names it
    fname = _normalise(filename.replace("_", " ").replace("-", " "))
    scores: Dict[str, float] = {}

    for key, meta in doc_types().items():
        if key == "unknown":
            continue
        score = 0.0
        for phrase in meta.get("strong", []):
            hits = _count_phrase(body, phrase)
            if hits:
                score += STRONG_WEIGHT + min(hits - 1, 3) * 0.5
            if _count_phrase(head, phrase):
                score += TITLE_BONUS
            if _count_phrase(fname, phrase):
                score += FILENAME_WEIGHT
        for phrase in meta.get("keywords", []):
            hits = _count_phrase(body, phrase)
            if hits:
                score += KEYWORD_WEIGHT * min(hits, 3) / 3.0 + KEYWORD_WEIGHT * 0.5
            if _count_phrase(fname, phrase):
                score += FILENAME_WEIGHT * 0.5
        for phrase in meta.get("negative", []):
            if _count_phrase(head, phrase):
                score += NEGATIVE_WEIGHT
        if score > 0:
            scores[key] = round(score, 3)
    return scores


def classify_by_rules(text: str, filename: str = "") -> Classification:
    scores = score_types(text, filename)
    if not scores:
        return Classification(
            doc_type="unknown",
            confidence=0.0,
            method="rules",
            rationale="No recognised document-type vocabulary was found in the extracted text.",
            scores={},
            needs_manual_review=True,
        )

    ranked: List[Tuple[str, float]] = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_key, best_score = ranked[0]
    runner_score = ranked[1][1] if len(ranked) > 1 else 0.0

    # Confidence combines absolute evidence with the margin over the runner-up.
    absolute = min(best_score / 12.0, 1.0)
    margin = (best_score - runner_score) / best_score if best_score else 0.0
    confidence = round(min(0.98, 0.45 * absolute + 0.55 * min(margin * 1.6, 1.0) * absolute + absolute * 0.25), 3)

    rationale = "Matched {} (score {:.1f}){}".format(
        doc_label(best_key),
        best_score,
        "; next best {} (score {:.1f})".format(doc_label(ranked[1][0]), runner_score) if len(ranked) > 1 else "",
    )
    if confidence < CONFIDENT_THRESHOLD:
        # Never assert a type we are not confident about - the weak match is
        # kept in the rationale so a reviewer can see what was considered.
        return Classification(
            doc_type="unknown",
            confidence=confidence,
            method="rules",
            rationale="Weak evidence only. {}".format(rationale),
            scores=dict(ranked[:5]),
            needs_manual_review=True,
        )
    return Classification(
        doc_type=best_key,
        confidence=confidence,
        method="rules",
        rationale=rationale,
        scores=dict(ranked[:5]),
        needs_manual_review=False,
    )


def classify(text: str, filename: str = "", llm=None) -> Classification:
    """Rules first; a configured model is consulted only when the rules waver."""
    result = classify_by_rules(text, filename)
    if llm is None or not llm.available or result.confidence >= LLM_ASSIST_THRESHOLD:
        return result

    candidates = list(result.scores.keys())[:6] or sorted(doc_types().keys())[:20]
    suggestion = llm.classify_document(text=text, filename=filename, candidates=candidates)
    if not suggestion or not suggestion.get("doc_type"):
        return result

    llm_type = suggestion["doc_type"]
    llm_conf = float(suggestion.get("confidence") or 0.0)
    if llm_type not in doc_types():
        return result

    if llm_type == result.doc_type:
        combined = min(0.97, max(result.confidence, (result.confidence + llm_conf) / 2 + 0.15))
        return Classification(
            doc_type=llm_type,
            confidence=round(combined, 3),
            method="rules+llm",
            rationale="{}. Model agreed ({}).".format(result.rationale, suggestion.get("rationale", "")[:200]),
            scores=result.scores,
            needs_manual_review=combined < CONFIDENT_THRESHOLD,
        )

    # Disagreement: take the model's answer only when the rules were weak, and
    # cap the confidence so the disagreement stays visible downstream.
    if llm_conf > result.confidence + 0.2:
        conf = round(min(0.7, llm_conf * 0.8), 3)
        return Classification(
            doc_type=llm_type,
            confidence=conf,
            method="llm",
            rationale="Rules suggested {} but the model identified {} ({}). Flagged for review.".format(
                doc_label(result.doc_type), doc_label(llm_type), suggestion.get("rationale", "")[:200]
            ),
            scores=result.scores,
            needs_manual_review=True,
        )

    return Classification(
        doc_type=result.doc_type,
        confidence=round(max(0.2, result.confidence * 0.8), 3),
        method="rules",
        rationale="{}. Model proposed {} instead; confidence reduced and flagged for review.".format(
            result.rationale, doc_label(llm_type)
        ),
        scores=result.scores,
        needs_manual_review=True,
    )
