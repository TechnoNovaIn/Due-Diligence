"""PDF rendering with ReportLab (platypus)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

SEVERITY_COLORS = {
    "critical": colors.HexColor("#8b1a1a"),
    "high": colors.HexColor("#b3541e"),
    "medium": colors.HexColor("#8a6d1a"),
    "low": colors.HexColor("#2c6e49"),
    "informational": colors.HexColor("#39506b"),
}
INK = colors.HexColor("#15181d")
MUTED = colors.HexColor("#5b6472")
LINE = colors.HexColor("#c9cfd9")
PANEL = colors.HexColor("#f2f5f9")


def _styles():
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Times-Bold", fontSize=20,
                                leading=24, textColor=INK, alignment=TA_LEFT, spaceAfter=2),
        "subtitle": ParagraphStyle("st", parent=base["Normal"], fontName="Times-Roman", fontSize=9.5,
                                   textColor=MUTED, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Times-Bold", fontSize=13.5,
                             leading=17, textColor=INK, spaceBefore=16, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Times-Bold", fontSize=10,
                             textColor=MUTED, spaceBefore=9, spaceAfter=3),
        "body": ParagraphStyle("b", parent=base["Normal"], fontName="Times-Roman", fontSize=9.5,
                               leading=13.5, textColor=INK, spaceAfter=4),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontName="Times-Roman", fontSize=8,
                                leading=10.5, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontName="Times-Roman", fontSize=8,
                               leading=10.5, textColor=INK),
        "cellhead": ParagraphStyle("ch", parent=base["Normal"], fontName="Times-Bold", fontSize=7.5,
                                   leading=9.5, textColor=INK),
        "callout": ParagraphStyle("co", parent=base["Normal"], fontName="Times-Roman", fontSize=9,
                                  leading=12.5, textColor=INK, backColor=PANEL,
                                  borderPadding=7, borderColor=LINE, borderWidth=0.6, spaceAfter=8),
    }
    return s


def _esc(value: Any) -> str:
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("“", '"').replace("”", '"'))


def _badge(severity: Optional[str]) -> str:
    if not severity:
        return "—"
    color = SEVERITY_COLORS.get(severity, MUTED)
    return '<font color="#{}"><b>{}</b></font>'.format(color.hexval()[4:], severity.upper())


def render_pdf(case, report, payload: Dict[str, Any], out_path: Path) -> Path:
    st = _styles()
    story: List[Any] = []
    p = payload

    def para(text, style="body"):
        story.append(Paragraph(_esc(text), st[style]))

    def raw(text, style="body"):
        story.append(Paragraph(text, st[style]))

    def heading(text):
        story.append(Paragraph(_esc(text), st["h2"]))

    def sub(text):
        story.append(Paragraph(_esc(text), st["h3"]))

    def bullets(items, style="body"):
        items = [i for i in items if i]
        if not items:
            return
        story.append(ListFlowable(
            [ListItem(Paragraph(_esc(i), st[style]), leftIndent=10) for i in items],
            bulletType="bullet", start="•", leftIndent=12, bulletFontSize=7,
        ))
        story.append(Spacer(1, 3))

    def table(headers, rows, widths=None, aligns=None):
        if not rows:
            return
        data = [[Paragraph(_esc(h), st["cellhead"]) for h in headers]]
        for row in rows:
            data.append([c if hasattr(c, "wrapOn") else Paragraph(
                c if isinstance(c, str) and c.startswith("<") else _esc(c), st["cell"]) for c in row])
        t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    # ---------------- cover ----------------
    para("Property Due Diligence Report", "title")
    s1 = p["section_1_executive_summary"]
    para("{} · Case {} · Version {} · Generated {}".format(
        case.property_name, case.case_ref, report.version, p["meta"]["generated_at"]), "subtitle")
    raw("<b>Scope and limitations.</b> " + _esc(p["meta"]["disclaimer"]), "callout")

    # ---------------- 1 ----------------
    heading("1. Executive summary")
    oc = s1["open_findings_by_severity"]
    table(["Documents received", "Analysed", "Pending", "Open requirements", "Critical", "High", "Overall risk"],
          [[s1["documents_received"], s1["documents_analysed"], s1["documents_pending"],
            s1["open_requirements"], oc.get("critical", 0), oc.get("high", 0),
            s1["overall_risk"].title()]],
          widths=[26*mm, 20*mm, 18*mm, 30*mm, 18*mm, 16*mm, 24*mm])
    prop = s1["property"]
    para("Property: {}{}{}{} · {} · {}".format(
        prop["name"],
        ", Sy. No. {}".format(prop["survey_number"]) if prop["survey_number"] else "",
        ", {}".format(prop["village"]) if prop["village"] else "",
        ", {}".format(prop["district"]) if prop["district"] else "",
        (prop["property_type"] or "").replace("_", " ").title(),
        (prop["transaction_type"] or "").replace("_", " ").title()))
    para("Purpose: {}".format(s1["purpose"]))
    raw("<b>Current status: {}</b>".format(_esc(s1["assessment_label"])))
    bullets(s1["status_explanation"])
    if s1["major_findings"]:
        sub("Major findings")
        table(["Ref", "Severity", "Finding", "Recommended action"],
              [[f["risk_ref"], _badge(f["severity"]), f["title"], f["action"]] for f in s1["major_findings"]],
              widths=[14*mm, 20*mm, 70*mm, 66*mm])
    if s1["recommended_next_steps"]:
        sub("Recommended next steps")
        bullets(s1["recommended_next_steps"])

    # ---------------- 2 ----------------
    heading("2. Property details")
    s2 = p["section_2_property_details"]
    sub("Recorded on the case")
    table(["Field", "Value"], [[k, v] for k, v in s2["declared_by_user"].items() if v],
          widths=[45*mm, 125*mm])
    sub("Consolidated from the documents")
    table(["Field", "Value", "Status", "Source"],
          [[r["label"], r["value"] or "—", r["status"].replace("_", " ").title(),
            "; ".join(r["sources"]) or r["note"]] for r in s2["from_documents"]],
          widths=[32*mm, 46*mm, 24*mm, 68*mm])
    para(s2["note"], "small")

    # ---------------- 3 ----------------
    heading("3. Document inventory")
    table(["File", "Type", "Date", "Status", "Pages", "Extraction", "Issues"],
          [[d["filename"], d["document_type"], d["document_date"],
            d["status"].replace("_", " ").title(),
            "{}/{}".format(d["pages_analysed"], d["pages"]),
            "{:.0%}{}".format(d["extraction_confidence"], " (OCR)" if d["ocr_used"] else ""),
            "; ".join(x for x in d["issues"] if x) or "—"]
           for d in p["section_3_document_inventory"]],
          widths=[36*mm, 32*mm, 18*mm, 20*mm, 13*mm, 18*mm, 33*mm])

    # ---------------- 4 ----------------
    heading("4. Individual document analysis")
    for d in p["section_4_document_analysis"]:
        block: List[Any] = [Paragraph("<b>{}</b> — {} ({})".format(
            _esc(d["filename"]), _esc(d["document_type"]), _esc(d["status"].replace("_", " "))), st["body"])]
        block.append(Paragraph(_esc(d["purpose"]), st["body"]))
        if d.get("summary"):
            block.append(Paragraph(_esc(d["summary"]), st["body"]))
        if d["parties"]:
            block.append(Paragraph("<b>Parties:</b> " + _esc("; ".join(
                "{} ({})".format(x["name"], x["role"]) for x in d["parties"])), st["body"]))
        if d["important_dates"]:
            block.append(Paragraph("<b>Dates:</b> " + _esc("; ".join(
                "{}: {}".format(x["label"], x["value"]) for x in d["important_dates"])), st["body"]))
        if d["property_identifiers"]:
            block.append(Paragraph("<b>Identifiers:</b> " + _esc("; ".join(
                "{}: {} (p.{})".format(x["label"], x["value"], x["page"])
                for x in d["property_identifiers"])), st["body"]))
        block.append(Paragraph("<b>Effect:</b> " + _esc(d["legal_or_financial_effect"]), st["body"]))
        for label, key in (("References", "referenced_documents"),
                           ("Internal inconsistencies", "internal_inconsistencies"),
                           ("Requires verification", "items_requiring_verification"),
                           ("Issues", "issues")):
            vals = [v for v in (d.get(key) or []) if v]
            if vals:
                block.append(Paragraph("<b>{}:</b> ".format(label) + _esc("; ".join(str(v) for v in vals)),
                                       st["small"]))
        block.append(Spacer(1, 7))
        story.append(KeepTogether(block))

    # ---------------- 5 ----------------
    heading("5. Ownership and title history")
    s5 = p["section_5_ownership_history"]
    if s5["timeline"]:
        table(["#", "From", "To", "Transfer", "Date", "Document", "Registration", "Status"],
              [[t["sequence"], ("[GAP] " if t["gap_before"] else "") + str(t["from_owner"]),
                t["to_owner"], t["transfer_type"], t["date"], t["document"],
                t["registration_ref"], t["verification_status"].title()]
               for t in s5["timeline"]],
              widths=[8*mm, 26*mm, 26*mm, 22*mm, 20*mm, 32*mm, 22*mm, 20*mm])
    else:
        para("No transfer document on record, so no ownership timeline could be constructed.")
    para(s5["note"], "small")

    # ---------------- 6 ----------------
    heading("6. Cross-document verification")
    rows = []
    for c in p["section_6_cross_verification"]["comparisons"]:
        detail = "\n".join("{} — {}".format(v["value"], ", ".join(v["documents"]))
                           for v in c["values"]) or "Not stated in any document."
        rows.append([c["label"], "Consistent" if c["consistent"] else "DIFFERS", detail])
    table(["Field", "Consistent?", "Values and sources"], rows, widths=[38*mm, 24*mm, 108*mm])

    # ---------------- 7 ----------------
    heading("7. Encumbrance and liability assessment")
    s7 = p["section_7_encumbrance"]
    if s7["encumbrance_certificates"]:
        table(["Certificate", "From", "To", "Nil?", "Entries"],
              [[e["document"], e["from"], e["to"], "Yes" if e["declares_nil"] else "No",
                e["entries_detected"]] for e in s7["encumbrance_certificates"]],
              widths=[60*mm, 28*mm, 28*mm, 16*mm, 38*mm])
    else:
        para("No Encumbrance Certificate is on record.")
    if s7["mortgage_indications"]:
        sub("Charge / mortgage indications")
        bullets(["{} (p.{}) — {}".format(m["document"], m["page"], (m["signal"] or "").replace("_", " "))
                 for m in s7["mortgage_indications"]], "small")
    if s7["findings"]:
        sub("Open encumbrance findings")
        table(["Ref", "Severity", "Finding"],
              [[f["risk_ref"], _badge(f["severity"]), f["title"]] for f in s7["findings"]],
              widths=[14*mm, 20*mm, 136*mm])
    raw("<b>Limitations of the encumbrance evidence</b>", "h3")
    bullets(s7["limitations"], "small")

    # ---------------- 8 ----------------
    heading("8. Legal and regulatory review")
    s8 = p["section_8_legal_regulatory"]
    if s8["approvals_on_record"]:
        table(["Type", "Value", "Document", "Page"],
              [[a["label"], a["value"], a["document"], a["page"]] for a in s8["approvals_on_record"]],
              widths=[34*mm, 54*mm, 62*mm, 12*mm])
    if s8["litigation_references"]:
        sub("Litigation references found in the documents")
        bullets(["{} (p.{}) — {}".format(l["document"], l["page"], (l["signal"] or "").replace("_", " "))
                 for l in s8["litigation_references"]], "small")
        para("A reference in a document is not evidence that a proceeding is currently pending or decided.",
             "small")
    else:
        para("No litigation reference was found in the supplied documents. This is not evidence that no "
             "litigation exists - no court record has been searched.")
    sub("What was and was not checked")
    bullets(["Completed: " + c for c in s8["checks_completed"]], "small")
    bullets(["On supplied documents only: " + c for c in s8["checks_on_supplied_documents_only"]], "small")
    bullets(["Outstanding: {} ({})".format(c["name"], c["authority"]) for c in s8["checks_outstanding"]],
            "small")

    # ---------------- 9 ----------------
    story.append(PageBreak())
    heading("9. Risk register")
    s9 = p["section_9_risk_register"]
    if s9["critical_and_high"]:
        raw("<b>Critical and high-priority findings</b>", "h3")
        bullets(["{} {} — {}".format(r["risk_ref"], r["severity"].upper(), r["description"])
                 for r in s9["critical_and_high"]])
    rows = []
    for r in s9["register"]:
        evidence = "; ".join(
            "{}{}".format(e["document"], " p.{}".format(e["page"]) if e["page"] else "")
            for e in r["evidence"]) or "—"
        rows.append([
            r["risk_ref"],
            "{}\n{}".format(r["description"], r["detail"]),
            _badge(r["severity"]),
            evidence,
            r["impact"],
            r["recommended_action"],
            r["status"].replace("_", " ").title(),
        ])
    table(["Ref", "Finding", "Severity", "Evidence", "Potential impact", "Recommended action", "Status"],
          rows, widths=[12*mm, 46*mm, 17*mm, 26*mm, 28*mm, 29*mm, 16*mm])

    # ---------------- 10 ----------------
    heading("10. Missing and pending documents")
    s10 = p["section_10_missing_documents"]
    para(s10["note"], "small")
    for title, group_rows in s10["groups"].items():
        sub(title)
        table(["Requirement", "Priority", "Why / risk if absent", "Where to obtain", "Next action", "Status"],
              [[r["name"], r["priority"].replace("_", " ").title(),
                "{}\nRisk: {}".format(r["reason"] or "", r["risk_if_absent"] or ""),
                r["issuing_authority"], r["next_action"], r["status"].replace("_", " ").title()]
               for r in group_rows],
              widths=[38*mm, 18*mm, 42*mm, 34*mm, 30*mm, 20*mm])
    raw("<b>Jurisdiction caveat.</b> " + _esc(s10["jurisdiction_caveat"]), "callout")

    # ---------------- 11 ----------------
    heading("11. Questions for the seller or property owner")
    questions = p["section_11_questions"]
    if questions:
        story.append(ListFlowable(
            [ListItem(Paragraph("{}<br/><font size=7 color='#5b6472'>Why: {}</font>".format(
                _esc(q["question"]), _esc(q["reason"])), st["body"])) for q in questions],
            bulletType="1", leftIndent=14))
        story.append(Spacer(1, 6))
    else:
        para("No outstanding question arises from the current evidence.")

    # ---------------- 12 ----------------
    heading("12. Recommended action plan")
    table(["#", "Group", "Action", "Because", "Depends on"],
          [[a["order"], a["group"], a["action"], a["reason"], "; ".join(a.get("depends_on") or []) or "—"]
           for a in p["section_12_action_plan"]],
          widths=[9*mm, 30*mm, 58*mm, 48*mm, 25*mm])

    # ---------------- 13 ----------------
    heading("13. Final assessment")
    s13 = p["section_13_final_assessment"]
    raw("<b>{}</b><br/>Overall risk level: {} &nbsp; Risk score: {} ({}/100 indicative)".format(
        _esc(s13["label"]), _badge(s13["overall_risk"]), s13["risk_score"],
        s13["risk_score_normalised"]), "callout")
    para("How this was determined: {}".format(s13["how_determined"]))
    bullets(s13["reasons"])
    sub("Scope and limitations")
    bullets(s13["scope_and_limitations"])
    raw("<b>Disclaimer.</b> " + _esc(s13["disclaimer"]), "callout")

    heading("Change history for this version")
    bullets(["{}: {}".format(c["type"].replace("_", " ").title(), c["detail"])
             for c in p.get("change_summary", [])])

    meta = p["meta"]
    footer_text = (
        "Report version {} · system {} · ruleset {} · AI: {} ({}) — {} · OCR {} · Jurisdiction {} ({})"
    ).format(
        report.version, meta["system_version"], meta["ruleset_version"],
        meta["ai"]["provider"], meta["ai"]["model"],
        "document text sent to a remote provider"
        if meta["ai"]["sends_document_text_off_device"] else "all processing local",
        "available" if meta["ocr"]["available"] else "not installed",
        meta["jurisdiction"]["name"],
        "confirmed" if meta["jurisdiction"]["confirmed_by_professional"] else "not confirmed by local counsel",
    )
    story.append(Spacer(1, 10))
    para(footer_text, "small")

    _build(out_path, story, case, report)
    return out_path


def _build(out_path: Path, story, case, report) -> None:
    doc = BaseDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
        title="Due Diligence Report v{} - {}".format(report.version, case.property_name),
        author="Property Due Diligence System", subject="Property due diligence",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

    def on_page(canvas, document):
        canvas.saveState()
        canvas.setFont("Times-Roman", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, 12 * mm,
                          "{} · Case {} · Report v{}".format(case.property_name, case.case_ref,
                                                             report.version))
        canvas.drawRightString(A4[0] - doc.rightMargin, 12 * mm, "Page {}".format(document.page))
        canvas.setStrokeColor(LINE)
        canvas.line(doc.leftMargin, 15 * mm, A4[0] - doc.rightMargin, 15 * mm)
        canvas.drawCentredString(A4[0] / 2, 7 * mm,
                                 "Preliminary automated assessment - not a legal opinion or title search")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=on_page)])
    doc.build(story)
