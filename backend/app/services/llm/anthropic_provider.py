"""Anthropic provider using tool-use for schema-validated structured output."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import CLASSIFY_SCHEMA, CROSS_SCHEMA, SUMMARY_SCHEMA, LLMProvider
from .prompts import SYSTEM_PROMPT, classification_prompt, cross_document_prompt, summary_prompt

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int = 4096, timeout: int = 120,
                 max_retries: int = 3, max_chars: int = 60000, base_url: Optional[str] = None) -> None:
        super().__init__(name="anthropic", model=model, available=False, remote=True)
        self.max_tokens = max_tokens
        self.max_chars = max_chars
        self.max_retries = max_retries
        try:
            import anthropic

            kwargs: Dict[str, Any] = {"api_key": api_key, "timeout": timeout, "max_retries": 0}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = anthropic.Anthropic(**kwargs)
            self.available = True
        except Exception as exc:  # pragma: no cover - import/credential failure
            self.last_error = "Anthropic client could not be created: {}".format(exc)
            self._client = None

    # ------------------------------------------------------------------
    def _structured_call(self, prompt: str, schema: Dict[str, Any], tool_name: str) -> Optional[Dict[str, Any]]:
        if not self._client:
            return None
        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                self.usage.calls += 1
                resp = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=SYSTEM_PROMPT,
                    tools=[{
                        "name": tool_name,
                        "description": "Return the structured result.",
                        "input_schema": schema,
                    }],
                    tool_choice={"type": "tool", "name": tool_name},
                    messages=[{"role": "user", "content": prompt}],
                )
                if getattr(resp, "usage", None):
                    self.usage.input_tokens += getattr(resp.usage, "input_tokens", 0) or 0
                    self.usage.output_tokens += getattr(resp.usage, "output_tokens", 0) or 0
                for block in resp.content:
                    if getattr(block, "type", None) == "tool_use":
                        return dict(block.input)
                return None
            except Exception as exc:  # pragma: no cover - network dependent
                self.usage.errors += 1
                self.last_error = str(exc)[:400]
                log.warning("LLM call failed (attempt %s/%s): %s", attempt, self.max_retries, exc)
                if attempt == self.max_retries:
                    return None
                time.sleep(delay)
                delay *= 2
        return None

    # ------------------------------------------------------------------
    def classify_document(self, text: str, filename: str, candidates: List[str]) -> Optional[Dict[str, Any]]:
        prompt = classification_prompt(text, filename, candidates, self.max_chars)
        out = self._structured_call(prompt, CLASSIFY_SCHEMA, "report_document_type")
        if not out:
            return None
        try:
            out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0))))
        except (TypeError, ValueError):
            out["confidence"] = 0.0
        return out

    def summarise_document(self, doc_type_label: str, text: str, known_fields: str) -> Optional[Dict[str, Any]]:
        prompt = summary_prompt(doc_type_label, text, known_fields, self.max_chars)
        return self._structured_call(prompt, SUMMARY_SCHEMA, "report_document_summary")

    def cross_document_observations(self, context_json: str) -> List[Dict[str, Any]]:
        prompt = cross_document_prompt(context_json[: self.max_chars])
        out = self._structured_call(prompt, CROSS_SCHEMA, "report_observations")
        if not out:
            return []
        observations = out.get("observations") or []
        return [o for o in observations if isinstance(o, dict) and o.get("title") and o.get("detail")]
