"""Offline provider: no network, no model.

The system is fully functional with this provider - classification, extraction,
cross-verification, requirements, risk and reporting are all deterministic.
What is lost is narrative summarisation and the open-ended second look over the
assembled evidence; both are clearly reported as not performed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import LLMProvider


class OfflineProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(name="offline", model="deterministic-rules", available=False, remote=False)

    def describe(self) -> Dict[str, Any]:
        info = super().describe()
        info["note"] = (
            "No language model is configured. Document contents never leave this machine. "
            "Classification, field extraction, cross-document verification, the requirement "
            "checklist and risk scoring run entirely on deterministic rules; narrative "
            "summarisation and open-ended cross-document review are not performed."
        )
        return info
