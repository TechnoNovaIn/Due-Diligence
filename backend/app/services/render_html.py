# -*- coding: utf-8 -*-
"""HTML rendering of a report payload, in English or Kannada."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..i18n import ASSESSMENT_STATUS, DOC_STATUS, SEVERITY, normalise_language, term
from .report_i18n import DISCLAIMER_KN, rt

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(case, report, payload: Dict[str, Any], lang: str = "en") -> str:
    lang = normalise_language(lang)
    template = _env.get_template("report.html.j2")
    final = payload.get("section_13_final_assessment", {}) or {}
    summary = payload.get("section_1_executive_summary", {}) or {}
    return template.render(
        case=case,
        report=report,
        p=payload,
        lang=lang,
        t=lambda key: rt(key, lang),
        sev=lambda value: term("severity", value, lang),
        doc_status=lambda value: term("doc_status", value, lang),
        tr=lambda vocabulary, value: term(vocabulary, value, lang),
        #: A Kannada report must carry the Kannada disclaimer verbatim, not a
        #: word-by-word rendering of the English one.
        disclaimer=(DISCLAIMER_KN if lang == "kn" else payload.get("meta", {}).get("disclaimer", "")),
        assessment_label=(
            term("assessment_status", final.get("status") or summary.get("assessment_status"), lang)
            if lang == "kn" else (final.get("label") or summary.get("assessment_label", ""))
        ),
    )
