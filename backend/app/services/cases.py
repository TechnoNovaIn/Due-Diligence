"""Case creation and folder provisioning."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..enums import CaseStatus
from ..models import Case
from . import audit, filesafe

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")

README = """This folder is monitored by the Property Due Diligence System.

Case: {ref} - {name}

Add every document relating to this property here. Sub-folders are fine.
Supported formats: PDF, DOCX, DOC, RTF, TXT, JPG, JPEG, PNG, TIFF, BMP, WEBP.

The system detects new and replaced files automatically, reads them, compares
them against the documents already on record, updates the risk register and the
missing-document checklist, and produces a new report version.

Nothing here is deleted or modified by the system. Removing a file flags the
corresponding document as removed; it does not erase the history of what was
assessed.
"""


def next_case_ref(session: Session) -> str:
    year = datetime.utcnow().year
    prefix = "PDD-{}-".format(year)
    count = session.scalar(
        select(func.count()).select_from(Case).where(Case.case_ref.like(prefix + "%"))
    ) or 0
    for n in range(count + 1, count + 500):
        ref = "{}{:04d}".format(prefix, n)
        exists = session.scalar(select(func.count()).select_from(Case).where(Case.case_ref == ref))
        if not exists:
            return ref
    raise RuntimeError("Could not allocate a case reference")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "property").strip()).strip("-")[:48] or "property"


def create_case(session: Session, data: Dict[str, Any], actor: str = "system") -> Case:
    settings = get_settings()
    ref = next_case_ref(session)

    folder = data.get("watch_folder")
    if folder:
        path = Path(folder).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        resolved = filesafe.resolve_within(path, settings.allowed_watch_roots + [path.resolve()])
    else:
        resolved = Path(settings.cases_root) / "{}_{}".format(ref, _slug(data.get("property_name", "")))
        resolved.mkdir(parents=True, exist_ok=True)

    readme = resolved / "README.txt"
    if not readme.exists():
        readme.write_text(README.format(ref=ref, name=data.get("property_name", "")), encoding="utf-8")

    case = Case(
        case_ref=ref,
        property_name=data["property_name"],
        address=data.get("address"),
        survey_number=data.get("survey_number"),
        subdivision_number=data.get("subdivision_number"),
        khata_number=data.get("khata_number"),
        plot_number=data.get("plot_number"),
        flat_number=data.get("flat_number"),
        village=data.get("village"),
        taluk=data.get("taluk"),
        district=data.get("district"),
        state=data.get("state"),
        jurisdiction_code=(data.get("jurisdiction_code") or settings.jurisdiction_default).upper(),
        property_type=data["property_type"],
        property_classification=data.get("property_classification"),
        land_area_value=data.get("land_area_value"),
        land_area_unit=data.get("land_area_unit"),
        dimensions=data.get("dimensions"),
        claimed_owner=data.get("claimed_owner"),
        seller_name=data.get("seller_name"),
        buyer_name=data.get("buyer_name"),
        transaction_type=data.get("transaction_type") or "purchase",
        purpose=data.get("purpose"),
        assigned_reviewer=data.get("assigned_reviewer"),
        watch_folder=str(resolved),
        watch_enabled=data.get("watch_enabled", True),
        status=CaseStatus.AWAITING_DOCUMENTS.value,
        extra={},
    )
    session.add(case)
    session.flush()
    audit.record(session, "case_created", case_id=case.id, actor=actor,
                 message="Case {} created for {}.".format(ref, case.property_name),
                 payload={"watch_folder": case.watch_folder,
                          "property_type": case.property_type,
                          "jurisdiction": case.jurisdiction_code})
    return case
