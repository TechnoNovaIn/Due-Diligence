"""Explainable risk scoring and overall assessment classification.

The numerical score is a *secondary* signal.  The overall classification is
driven by the worst unresolved finding and by whether the mandatory checks have
actually been completed, so one serious issue can never be averaged away.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..enums import (
    ASSESSMENT_LABELS,
    OPEN_REQUIREMENT_STATUSES,
    SEVERITY_ORDER,
    SEVERITY_WEIGHT,
    AssessmentStatus,
    FindingStatus,
    Priority,
    RequirementCategory,
    RequirementStatus,
    Severity,
)

#: How much an unconfirmed (suspected) finding counts relative to a confirmed one.
SUSPECTED_FACTOR = 0.7
#: How much an accepted-risk finding still contributes.
ACCEPTED_FACTOR = 0.25
#: Scores are normalised against this for the 0-100 display figure.
SCORE_NORMALISER = 300.0


def score_finding(severity: str, confidence: float, confirmed: bool, status: str) -> float:
    """Severity x evidence reliability x whether the issue is still open."""
    base = SEVERITY_WEIGHT.get(Severity(severity) if not isinstance(severity, Severity) else severity,
                               SEVERITY_WEIGHT[Severity.INFORMATIONAL])
    reliability = 0.5 + 0.5 * max(0.0, min(1.0, confidence or 0.0))
    confirmation = 1.0 if confirmed else SUSPECTED_FACTOR
    if status == FindingStatus.OPEN.value:
        openness = 1.0
    elif status == FindingStatus.ACCEPTED.value:
        openness = ACCEPTED_FACTOR
    else:
        openness = 0.0
    return round(base * reliability * confirmation * openness, 2)


def _severity_rank(sev: str) -> int:
    try:
        return SEVERITY_ORDER[Severity(sev)]
    except (ValueError, KeyError):
        return SEVERITY_ORDER[Severity.INFORMATIONAL]


def summarise_findings(findings: Sequence[Any]) -> Dict[str, Any]:
    counts = {s.value: 0 for s in Severity}
    open_counts = {s.value: 0 for s in Severity}
    total_score = 0.0
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
        if f.status == FindingStatus.OPEN.value:
            open_counts[f.severity] = open_counts.get(f.severity, 0) + 1
        total_score += score_finding(f.severity, f.confidence, f.confirmed, f.status)
    return {
        "counts": counts,
        "open_counts": open_counts,
        "total": len(findings),
        "open_total": sum(open_counts.values()),
        "score": round(total_score, 2),
        "score_normalised": round(min(100.0, total_score / SCORE_NORMALISER * 100.0), 1),
    }


def overall_risk(findings: Sequence[Any]) -> str:
    """The worst unresolved finding sets the overall level - never an average."""
    worst = Severity.INFORMATIONAL.value
    for f in findings:
        if f.status not in (FindingStatus.OPEN.value, FindingStatus.ACCEPTED.value):
            continue
        if f.status == FindingStatus.ACCEPTED.value and _severity_rank(f.severity) < _severity_rank(Severity.HIGH.value):
            continue
        if _severity_rank(f.severity) < _severity_rank(worst):
            worst = f.severity
    return worst


def assess(findings: Sequence[Any], requirements: Sequence[Any], documents_pending: int,
           documents_total: int, documents_analysed: int) -> Dict[str, Any]:
    """Classify the case and explain, in words, how the classification was reached."""
    summary = summarise_findings(findings)
    risk = overall_risk(findings)
    reasons: List[str] = []

    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    open_reqs = [r for r in requirements if r.status in open_statuses]
    open_mandatory = [r for r in open_reqs if r.priority == Priority.MANDATORY.value]
    open_statutory = [r for r in open_reqs if r.category == RequirementCategory.STATUTORY.value]
    external_pending = [r for r in open_reqs if r.category in (
        RequirementCategory.EXTERNAL_CHECK.value, RequirementCategory.PROFESSIONAL.value)]
    discrepancy_pending = [r for r in open_reqs if r.category == RequirementCategory.DISCREPANCY.value]

    critical_open = summary["open_counts"].get(Severity.CRITICAL.value, 0)
    high_open = summary["open_counts"].get(Severity.HIGH.value, 0)
    medium_open = summary["open_counts"].get(Severity.MEDIUM.value, 0)

    if documents_total == 0:
        status = AssessmentStatus.INCOMPLETE
        reasons.append("No documents have been added to this case.")
    elif documents_pending > 0:
        status = AssessmentStatus.INCOMPLETE
        reasons.append("{} document(s) are still being processed, so the assessment is not yet "
                       "complete.".format(documents_pending))
    elif critical_open or high_open:
        status = AssessmentStatus.HIGH_RISK
        reasons.append("{} critical and {} high-severity finding(s) are unresolved.".format(
            critical_open, high_open))
    elif open_mandatory:
        status = AssessmentStatus.INCOMPLETE
        reasons.append("{} mandatory requirement(s) have not been met: {}.".format(
            len(open_mandatory), "; ".join(r.name for r in open_mandatory[:3])))
    elif medium_open or discrepancy_pending:
        status = AssessmentStatus.FURTHER_VERIFICATION
        reasons.append("{} medium-severity finding(s) and {} discrepancy-driven requirement(s) remain "
                       "open.".format(medium_open, len(discrepancy_pending)))
    elif external_pending:
        status = AssessmentStatus.READY_FOR_REVIEW
        reasons.append("No unresolved findings above low severity remain in the supplied documents, but "
                       "{} external check(s) or professional review(s) have not been performed.".format(
                           len(external_pending)))
    elif open_reqs:
        status = AssessmentStatus.FURTHER_VERIFICATION
        reasons.append("{} recommended requirement(s) remain open.".format(len(open_reqs)))
    else:
        status = AssessmentStatus.NO_MATERIAL_ISSUES
        reasons.append("Every tracked requirement has been met and no finding above low severity is open.")

    if open_statutory and status != AssessmentStatus.HIGH_RISK:
        reasons.append("{} statutory requirement(s) are still outstanding.".format(len(open_statutory)))
    if documents_total and documents_analysed < documents_total:
        reasons.append("{} of {} documents could not be analysed.".format(
            documents_total - documents_analysed, documents_total))

    scope = (
        "This classification reflects only the documents supplied in the case folder. No official record, "
        "court registry or external database has been checked, and no legal opinion has been given."
    )

    return {
        "assessment_status": status.value,
        "assessment_label": ASSESSMENT_LABELS[status],
        "explanation_kn": _explain_kn(status, critical_open, high_open, medium_open,
                                      open_mandatory, external_pending, discrepancy_pending,
                                      open_reqs, documents_pending, documents_total,
                                      documents_analysed, open_statutory),
        "overall_risk": risk,
        "risk_score": summary["score"],
        "risk_score_normalised": summary["score_normalised"],
        "counts": summary["counts"],
        "open_counts": summary["open_counts"],
        "open_findings": summary["open_total"],
        "open_requirements": len(open_reqs),
        "open_mandatory_requirements": len(open_mandatory),
        "external_checks_pending": len(external_pending),
        "explanation": reasons,
        "scope_statement": scope,
        "method": (
            "The overall level is set by the most severe unresolved finding, not by an average. The "
            "numerical score (severity x evidence reliability x whether the issue is confirmed and still "
            "open) is shown alongside it as a secondary indicator only."
        ),
        "method_kn": (
            "ಒಟ್ಟಾರೆ ಮಟ್ಟವನ್ನು ಅತ್ಯಂತ ಗಂಭೀರವಾದ ಇತ್ಯರ್ಥವಾಗದ ಅಂಶವು ನಿರ್ಧರಿಸುತ್ತದೆ, ಸರಾಸರಿ ಅಲ್ಲ. "
            "ಸಂಖ್ಯಾತ್ಮಕ ಅಂಕವನ್ನು (ತೀವ್ರತೆ x ಸಾಕ್ಷ್ಯದ ವಿಶ್ವಾಸಾರ್ಹತೆ x ಅಂಶ ದೃಢಪಟ್ಟಿದೆಯೇ ಮತ್ತು ಇನ್ನೂ "
            "ಬಾಕಿ ಇದೆಯೇ) ಜೊತೆಗೆ ದ್ವಿತೀಯ ಸೂಚಕವಾಗಿ ಮಾತ್ರ ತೋರಿಸಲಾಗಿದೆ."
        ),
        "scope_statement_kn": (
            "ಈ ವರ್ಗೀಕರಣವು ಪ್ರಕರಣದ ಫೋಲ್ಡರ್‌ನಲ್ಲಿ ಸಲ್ಲಿಸಿದ ದಾಖಲೆಗಳನ್ನು ಮಾತ್ರ ಆಧರಿಸಿದೆ. ಯಾವುದೇ "
            "ಅಧಿಕೃತ ದಾಖಲೆ, ನ್ಯಾಯಾಲಯ ದಾಖಲೆ ಅಥವಾ ಹೊರಗಿನ ಮಾಹಿತಿ ಕೋಶವನ್ನು ಪರಿಶೀಲಿಸಲಾಗಿಲ್ಲ, ಮತ್ತು "
            "ಯಾವುದೇ ಕಾನೂನು ಅಭಿಪ್ರಾಯ ನೀಡಲಾಗಿಲ್ಲ."
        ),
    }


def _explain_kn(status, critical_open, high_open, medium_open, open_mandatory, external_pending,
                discrepancy_pending, open_reqs, documents_pending, documents_total,
                documents_analysed, open_statutory) -> List[str]:
    """The same reasoning as `explanation`, written in Kannada."""
    out: List[str] = []
    if documents_total == 0:
        out.append("ಈ ಪ್ರಕರಣಕ್ಕೆ ಯಾವುದೇ ದಾಖಲೆ ಸೇರಿಸಲಾಗಿಲ್ಲ.")
    elif documents_pending > 0:
        out.append("{} ದಾಖಲೆ(ಗಳು) ಇನ್ನೂ ಪ್ರಕ್ರಿಯೆಯಲ್ಲಿವೆ, ಆದ್ದರಿಂದ ಮೌಲ್ಯಮಾಪನ ಪೂರ್ಣವಾಗಿಲ್ಲ."
                   .format(documents_pending))
    elif critical_open or high_open:
        out.append("{} ಅತಿ ಗಂಭೀರ ಮತ್ತು {} ಗಂಭೀರ ಅಂಶ(ಗಳು) ಇತ್ಯರ್ಥವಾಗಿಲ್ಲ."
                   .format(critical_open, high_open))
    elif open_mandatory:
        out.append("{} ಕಡ್ಡಾಯ ಅಗತ್ಯ(ಗಳು) ಪೂರೈಸಿಲ್ಲ: {}."
                   .format(len(open_mandatory), "; ".join(r.name for r in open_mandatory[:3])))
    elif medium_open or discrepancy_pending:
        out.append("{} ಮಧ್ಯಮ ತೀವ್ರತೆಯ ಅಂಶ(ಗಳು) ಮತ್ತು {} ವ್ಯತ್ಯಾಸ ಸಂಬಂಧಿತ ಅಗತ್ಯ(ಗಳು) ಬಾಕಿ ಇವೆ."
                   .format(medium_open, len(discrepancy_pending)))
    elif external_pending:
        out.append("ಸಲ್ಲಿಸಿದ ದಾಖಲೆಗಳಲ್ಲಿ ಕಡಿಮೆ ತೀವ್ರತೆಗಿಂತ ಮೇಲಿನ ಯಾವುದೇ ಅಂಶ ಬಾಕಿ ಇಲ್ಲ, ಆದರೆ "
                   "{} ಹೊರಗಿನ ಪರಿಶೀಲನೆ ಅಥವಾ ವೃತ್ತಿಪರ ಪರಿಶೀಲನೆ ನಡೆಸಲಾಗಿಲ್ಲ.".format(len(external_pending)))
    elif open_reqs:
        out.append("{} ಶಿಫಾರಸು ಮಾಡಿದ ಅಗತ್ಯ(ಗಳು) ಬಾಕಿ ಇವೆ.".format(len(open_reqs)))
    else:
        out.append("ಪ್ರತಿ ಅಗತ್ಯವನ್ನೂ ಪೂರೈಸಲಾಗಿದ್ದು, ಕಡಿಮೆ ತೀವ್ರತೆಗಿಂತ ಮೇಲಿನ ಯಾವುದೇ ಅಂಶ ಬಾಕಿ ಇಲ್ಲ.")

    if open_statutory and status != AssessmentStatus.HIGH_RISK:
        out.append("{} ಕಾನೂನಿನ ಪ್ರಕಾರ ಅಗತ್ಯವಾದ ದಾಖಲೆ(ಗಳು) ಇನ್ನೂ ಬಾಕಿ ಇವೆ.".format(len(open_statutory)))
    if documents_total and documents_analysed < documents_total:
        out.append("{} ದಾಖಲೆಗಳಲ್ಲಿ {} ದಾಖಲೆಯನ್ನು ವಿಶ್ಲೇಷಿಸಲಾಗಲಿಲ್ಲ."
                   .format(documents_total, documents_total - documents_analysed))
    return out


def priority_actions(findings: Sequence[Any], requirements: Sequence[Any]) -> List[Dict[str, Any]]:
    """An ordered action plan: worst findings first, then the documents they need."""
    actions: List[Dict[str, Any]] = []
    open_findings = [f for f in findings if f.status == FindingStatus.OPEN.value]
    open_findings.sort(key=lambda f: (_severity_rank(f.severity), -(f.confidence or 0)))

    open_statuses = {s.value for s in OPEN_REQUIREMENT_STATUSES}
    reqs_by_finding: Dict[str, List[Any]] = {}
    for r in requirements:
        if r.status in open_statuses and getattr(r, "related_finding_id", None):
            reqs_by_finding.setdefault(r.related_finding_id, []).append(r)

    order = 0
    for f in open_findings:
        if _severity_rank(f.severity) > SEVERITY_ORDER[Severity.MEDIUM]:
            continue
        order += 1
        depends = [r.name for r in reqs_by_finding.get(f.id, [])]
        actions.append({
            "order": order,
            "group": "Immediate" if _severity_rank(f.severity) <= SEVERITY_ORDER[Severity.HIGH] else "Resolve",
            "action": f.recommended_action or "Investigate and resolve.",
            "reason": f.title,
            "severity": f.severity,
            "depends_on": depends,
            "finding_id": f.id,
            "risk_ref": getattr(f, "risk_ref", None),
        })

    grouped: Dict[str, List[Any]] = {}
    for r in requirements:
        if r.status not in open_statuses:
            continue
        grouped.setdefault(r.category, []).append(r)

    group_titles = {
        RequirementCategory.STATUTORY.value: "Collect documents required by law",
        RequirementCategory.CONDITIONAL.value: "Collect conditionally required documents",
        RequirementCategory.DISCREPANCY.value: "Collect documents needed to resolve discrepancies",
        RequirementCategory.RECOMMENDED.value: "Recommended for stronger due diligence",
        RequirementCategory.EXTERNAL_CHECK.value: "Perform external verification",
        RequirementCategory.PROFESSIONAL.value: "Obtain professional review",
    }
    for category in (RequirementCategory.STATUTORY.value, RequirementCategory.DISCREPANCY.value,
                     RequirementCategory.CONDITIONAL.value, RequirementCategory.EXTERNAL_CHECK.value,
                     RequirementCategory.RECOMMENDED.value, RequirementCategory.PROFESSIONAL.value):
        for r in grouped.get(category, []):
            order += 1
            actions.append({
                "order": order,
                "group": group_titles.get(category, category),
                "action": r.next_action or "Obtain: {}".format(r.name),
                "reason": r.reason or r.name,
                "severity": None,
                "depends_on": [],
                "requirement_id": getattr(r, "id", None),
                "authority": r.issuing_authority,
            })
    return actions
