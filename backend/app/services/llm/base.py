"""Provider interface and structured-output schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class LLMUnavailable(RuntimeError):
    pass


@dataclass
class LLMUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: int = 0


CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
    "required": ["doc_type", "confidence", "rationale"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "purpose": {"type": "string"},
        "parties": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "role": {"type": "string"}},
                "required": ["name", "role"],
            },
        },
        "legal_effect": {"type": "string"},
        "referenced_documents": {"type": "array", "items": {"type": "string"}},
        "internal_inconsistencies": {"type": "array", "items": {"type": "string"}},
        "items_requiring_verification": {"type": "array", "items": {"type": "string"}},
        "silent_on": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["purpose", "legal_effect"],
}

CROSS_SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "informational"]},
                    "documents": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["title", "detail", "severity"],
            },
        }
    },
    "required": ["observations"],
}


@dataclass
class LLMProvider:
    """Base provider.  Subclasses override the capability methods they support."""

    name: str = "base"
    model: str = ""
    available: bool = False
    remote: bool = False
    usage: LLMUsage = field(default_factory=LLMUsage)
    last_error: Optional[str] = None

    # -- capabilities ----------------------------------------------------
    def classify_document(self, text: str, filename: str, candidates: List[str]) -> Optional[Dict[str, Any]]:
        return None

    def summarise_document(self, doc_type_label: str, text: str, known_fields: str) -> Optional[Dict[str, Any]]:
        return None

    def cross_document_observations(self, context_json: str) -> List[Dict[str, Any]]:
        return []

    # -- reporting -------------------------------------------------------
    def describe(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "available": self.available,
            "sends_document_text_off_device": self.remote,
            "calls": self.usage.calls,
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "errors": self.usage.errors,
            "last_error": self.last_error,
        }
