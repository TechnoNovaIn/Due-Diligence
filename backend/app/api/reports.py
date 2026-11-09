"""Report endpoints: list, detail, HTML preview, PDF export."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Case, Report
from ..schemas import ReportDetail, ReportOut
from ..services.report import generate_report
from .deps import Principal, current_principal, get_case, require_write
from .translate import get_lang

router = APIRouter(tags=["reports"])


@router.get("/cases/{case_id}/reports", response_model=List[ReportOut])
def list_reports(case: Case = Depends(get_case), db: Session = Depends(get_db),
                 principal: Principal = Depends(current_principal)) -> List[ReportOut]:
    reports = db.scalars(
        select(Report).where(Report.case_id == case.id).order_by(Report.version.desc())
    ).all()
    return [ReportOut.model_validate(r) for r in reports]


@router.post("/cases/{case_id}/reports", response_model=ReportOut, status_code=201)
def create_report(case: Case = Depends(get_case), db: Session = Depends(get_db),
                  principal: Principal = Depends(require_write)) -> ReportOut:
    report = generate_report(db, case, actor=principal.username)
    db.commit()
    db.refresh(report)
    return ReportOut.model_validate(report)


def _resolve(db: Session, case: Case, version: str) -> Report:
    if version == "latest":
        report = db.scalars(
            select(Report).where(Report.case_id == case.id).order_by(Report.version.desc())
        ).first()
    else:
        try:
            number = int(version)
        except ValueError:
            raise HTTPException(status_code=400, detail="Version must be a number or 'latest'")
        report = db.scalars(
            select(Report).where(Report.case_id == case.id, Report.version == number)
        ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No report has been generated for this case yet")
    return report


@router.get("/cases/{case_id}/reports/{version}", response_model=ReportDetail)
def report_detail(version: str, case: Case = Depends(get_case), db: Session = Depends(get_db),
                  principal: Principal = Depends(current_principal)) -> ReportDetail:
    return ReportDetail.model_validate(_resolve(db, case, version))


@router.get("/cases/{case_id}/reports/{version}/html", response_class=HTMLResponse)
def report_html(version: str, case: Case = Depends(get_case), db: Session = Depends(get_db),
                principal: Principal = Depends(current_principal),
                lang: str = Depends(get_lang)) -> HTMLResponse:
    """The English report is served from disk; other languages render on demand."""
    report = _resolve(db, case, version)
    from ..services.render_html import render_html

    if lang == "en" and report.html_path and Path(report.html_path).exists():
        return HTMLResponse(Path(report.html_path).read_text(encoding="utf-8"))
    return HTMLResponse(render_html(case, report, report.payload, lang))


@router.get("/cases/{case_id}/reports/{version}/pdf")
def report_pdf(version: str, case: Case = Depends(get_case), db: Session = Depends(get_db),
               principal: Principal = Depends(current_principal),
               lang: str = Depends(get_lang)) -> FileResponse:
    from ..config import get_settings

    report = _resolve(db, case, version)
    out_dir = Path(get_settings().reports_dir) / case.case_ref
    out_dir.mkdir(parents=True, exist_ok=True)

    if lang == "kn":
        # ReportLab does not shape Kannada conjuncts, so the Kannada PDF is laid
        # out through MuPDF's HTML engine instead. It is cached next to the
        # English one.
        from ..services.render_html import render_html
        from ..services.render_pdf_kn import available, render_pdf_kannada

        if not available():
            raise HTTPException(
                status_code=503,
                detail=("No Kannada font is installed on this machine, so a Kannada PDF cannot be "
                        "produced. The Kannada report is available as HTML."))
        out = out_dir / "due-diligence-report-v{:03d}-kn.pdf".format(report.version)
        if not out.exists():
            html = render_html(case, report, report.payload, "kn")
            footer = "{} · {} · v{}".format(case.property_name, case.case_ref, report.version)
            try:
                render_pdf_kannada(html, out, footer=footer)
            except Exception as exc:
                raise HTTPException(status_code=500,
                                    detail="Kannada PDF generation failed: {}".format(exc))
        return FileResponse(str(out), media_type="application/pdf",
                            filename="{}-v{:03d}-kn.pdf".format(case.case_ref, report.version))

    if not report.pdf_path or not Path(report.pdf_path).exists():
        from ..services.render_pdf import render_pdf

        out = out_dir / "due-diligence-report-v{:03d}.pdf".format(report.version)
        try:
            render_pdf(case, report, report.payload, out)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="PDF generation failed: {}".format(exc))
        report.pdf_path = str(out)
        db.commit()
    return FileResponse(report.pdf_path, media_type="application/pdf",
                        filename="{}-due-diligence-v{:03d}.pdf".format(case.case_ref, report.version))


@router.get("/cases/{case_id}/reports/{version}/changes")
def report_changes(version: str, case: Case = Depends(get_case), db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    report = _resolve(db, case, version)
    return {"version": report.version, "generated_at": report.generated_at,
            "changes": report.change_summary or []}
