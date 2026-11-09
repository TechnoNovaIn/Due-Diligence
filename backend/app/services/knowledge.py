"""Loader for the rule data that drives classification and requirements."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
JURISDICTION_DIR = RULES_DIR / "jurisdictions"


@functools.lru_cache(maxsize=1)
def _raw_doc_types() -> Dict[str, Dict[str, Any]]:
    with open(RULES_DIR / "doc_types.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@functools.lru_cache(maxsize=1)
def doc_types() -> Dict[str, Dict[str, Any]]:
    """Flat ``{type_key: metadata}`` map; metadata carries its group.

    Kannada vocabulary lives in its own ``strong_kn`` / ``keywords_kn`` keys so a
    Kannada speaker can review it in isolation; it is merged into the scoring
    lists here, because classification itself is script-agnostic.
    """
    flat: Dict[str, Dict[str, Any]] = {}
    for group, members in _raw_doc_types().items():
        for key, meta in (members or {}).items():
            entry = dict(meta or {})
            entry.setdefault("label", key.replace("_", " ").title())
            entry.setdefault("label_kn", entry["label"])
            entry["key"] = key
            entry["group"] = group
            for field in ("strong", "keywords", "negative", "fields", "strong_kn", "keywords_kn"):
                entry.setdefault(field, [])
            entry["strong"] = list(entry["strong"]) + list(entry["strong_kn"])
            entry["keywords"] = list(entry["keywords"]) + list(entry["keywords_kn"])
            flat[key] = entry
    return flat


def doc_type_meta(key: Optional[str]) -> Dict[str, Any]:
    return doc_types().get(key or "unknown", doc_types()["unknown"])


def doc_label(key: Optional[str], lang: str = "en") -> str:
    if not key:
        return "ವರ್ಗೀಕರಿಸದ ದಾಖಲೆ" if lang == "kn" else "Unclassified"
    meta = doc_type_meta(key)
    if lang == "kn":
        return meta.get("label_kn") or meta.get("label", key)
    return meta.get("label", key)


def doc_labels(key: Optional[str]) -> Dict[str, str]:
    """Both labels, for an interface that can switch language without a round trip."""
    return {"en": doc_label(key, "en"), "kn": doc_label(key, "kn")}


def doc_group(key: Optional[str]) -> str:
    return doc_type_meta(key).get("group", "other")


#: Deed types that can themselves move title from one holder to another.
TITLE_TRANSFER_TYPES = {
    "sale_deed", "title_deed", "gift_deed", "partition_deed", "settlement_deed",
    "exchange_deed", "conveyance_deed", "mother_deed", "release_deed",
    "inheritance_document", "court_order_ownership", "apartment_deed",
}

#: Types whose presence indicates the property originated as agricultural land.
AGRICULTURAL_INDICATOR_TYPES = {"rtc_pahani", "land_conversion_order", "phodi_record", "tippani"}

MORTGAGE_TYPES = {"mortgage_deed", "loan_sanction_letter", "lien_document"}
MORTGAGE_RELEASE_TYPES = {"loan_closure_certificate", "bank_release_deed", "release_deed"}
LITIGATION_TYPES = {"court_judgment", "litigation_notice", "court_order_ownership",
                    "government_notice", "acquisition_notice"}
IDENTITY_TYPES = {"aadhaar", "pan_card", "identity_document"}

#: Document types whose extracted content is masked before it reaches a report.
SENSITIVE_TYPES = {"aadhaar", "pan_card", "identity_document"}


@functools.lru_cache(maxsize=16)
def jurisdiction(code: Optional[str] = None) -> Dict[str, Any]:
    """Load a jurisdiction rule set, falling back to the generic one."""
    code = (code or "DEFAULT").upper()
    path = JURISDICTION_DIR / f"{code}.yaml"
    if not path.exists():
        path = JURISDICTION_DIR / "DEFAULT.yaml"
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("code", code)
    data.setdefault("requirements", [])
    data.setdefault("authorities", {})
    return data


def available_jurisdictions() -> List[Dict[str, str]]:
    out = []
    for p in sorted(JURISDICTION_DIR.glob("*.yaml")):
        data = jurisdiction(p.stem)
        out.append({"code": data.get("code", p.stem), "name": data.get("name", p.stem)})
    return out


def authority_for(jur: Dict[str, Any], key: str, default: str = "The relevant issuing authority") -> str:
    return jur.get("authorities", {}).get(key, default)
