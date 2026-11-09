# -*- coding: utf-8 -*-
"""Report headings, standing text and the Kannada-capable PDF path."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Dict, List, Optional

REPORT_STRINGS: Dict[str, Dict[str, str]] = {
    "report.title": {"en": "Property Due Diligence Report", "kn": "ಸ್ವತ್ತು ಪರಿಶೀಲನಾ ವರದಿ"},
    "report.case": {"en": "Case", "kn": "ಪ್ರಕರಣ"},
    "report.version": {"en": "Version", "kn": "ಆವೃತ್ತಿ"},
    "report.generated": {"en": "Generated", "kn": "ಸಿದ್ಧಪಡಿಸಿದ್ದು"},
    "report.scopeHeading": {"en": "Scope and limitations.", "kn": "ವ್ಯಾಪ್ತಿ ಮತ್ತು ಮಿತಿಗಳು."},

    "s1": {"en": "1. Executive summary", "kn": "೧. ಕಾರ್ಯನಿರ್ವಾಹಕ ಸಾರಾಂಶ"},
    "s2": {"en": "2. Property details", "kn": "೨. ಸ್ವತ್ತಿನ ವಿವರಗಳು"},
    "s3": {"en": "3. Document inventory", "kn": "೩. ದಾಖಲೆಗಳ ಪಟ್ಟಿ"},
    "s4": {"en": "4. Individual document analysis", "kn": "೪. ಪ್ರತಿ ದಾಖಲೆಯ ವಿಶ್ಲೇಷಣೆ"},
    "s5": {"en": "5. Ownership and title history", "kn": "೫. ಮಾಲೀಕತ್ವ ಮತ್ತು ಹಕ್ಕಿನ ಇತಿಹಾಸ"},
    "s6": {"en": "6. Cross-document verification", "kn": "೬. ದಾಖಲೆಗಳ ಪರಸ್ಪರ ಪರಿಶೀಲನೆ"},
    "s7": {"en": "7. Encumbrance and liability assessment", "kn": "೭. ಋಣಭಾರ ಮತ್ತು ಬಾಧ್ಯತೆಯ ಮೌಲ್ಯಮಾಪನ"},
    "s8": {"en": "8. Legal and regulatory review", "kn": "೮. ಕಾನೂನು ಮತ್ತು ನಿಯಂತ್ರಣ ಪರಿಶೀಲನೆ"},
    "s9": {"en": "9. Risk register", "kn": "೯. ಅಪಾಯಗಳ ನೋಂದಣಿ"},
    "s10": {"en": "10. Missing and pending documents", "kn": "೧೦. ಕೊರತೆಯ ಮತ್ತು ಬಾಕಿ ದಾಖಲೆಗಳು"},
    "s11": {"en": "11. Questions for the seller or property owner",
            "kn": "೧೧. ಮಾರಾಟಗಾರರಿಗೆ ಅಥವಾ ಮಾಲೀಕರಿಗೆ ಪ್ರಶ್ನೆಗಳು"},
    "s12": {"en": "12. Recommended action plan", "kn": "೧೨. ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ ಯೋಜನೆ"},
    "s13": {"en": "13. Final assessment", "kn": "೧೩. ಅಂತಿಮ ಮೌಲ್ಯಮಾಪನ"},
    "s14": {"en": "Change history for this version", "kn": "ಈ ಆವೃತ್ತಿಯ ಬದಲಾವಣೆಗಳು"},

    "lbl.documentsReceived": {"en": "Documents received", "kn": "ಸ್ವೀಕರಿಸಿದ ದಾಖಲೆಗಳು"},
    "lbl.analysed": {"en": "Analysed", "kn": "ವಿಶ್ಲೇಷಿಸಲಾಗಿದೆ"},
    "lbl.openRequirements": {"en": "Open requirements", "kn": "ಬಾಕಿ ಅಗತ್ಯಗಳು"},
    "lbl.criticalHigh": {"en": "Critical & high findings", "kn": "ಅತಿ ಗಂಭೀರ ಮತ್ತು ಗಂಭೀರ ಅಂಶಗಳು"},
    "lbl.overallRisk": {"en": "Overall risk level", "kn": "ಒಟ್ಟಾರೆ ಅಪಾಯದ ಮಟ್ಟ"},
    "lbl.property": {"en": "Property", "kn": "ಸ್ವತ್ತು"},
    "lbl.purpose": {"en": "Purpose", "kn": "ಉದ್ದೇಶ"},
    "lbl.currentStatus": {"en": "Current status", "kn": "ಪ್ರಸ್ತುತ ಸ್ಥಿತಿ"},
    "lbl.majorFindings": {"en": "Major findings", "kn": "ಪ್ರಮುಖ ಅಂಶಗಳು"},
    "lbl.nextSteps": {"en": "Recommended next steps", "kn": "ಮುಂದಿನ ಶಿಫಾರಸು ಕ್ರಮಗಳು"},
    "lbl.ref": {"en": "Ref", "kn": "ಸಂಕೇತ"},
    "lbl.severity": {"en": "Severity", "kn": "ತೀವ್ರತೆ"},
    "lbl.finding": {"en": "Finding", "kn": "ಅಂಶ"},
    "lbl.recommendedAction": {"en": "Recommended action", "kn": "ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ"},
    "lbl.recordedOnCase": {"en": "Recorded on the case", "kn": "ಪ್ರಕರಣದಲ್ಲಿ ನಮೂದಿಸಿದ್ದು"},
    "lbl.consolidated": {"en": "Consolidated from the documents", "kn": "ದಾಖಲೆಗಳಿಂದ ಕ್ರೋಢೀಕರಿಸಿದ್ದು"},
    "lbl.field": {"en": "Field", "kn": "ವಿವರ"},
    "lbl.value": {"en": "Value", "kn": "ಮೌಲ್ಯ"},
    "lbl.status": {"en": "Status", "kn": "ಸ್ಥಿತಿ"},
    "lbl.source": {"en": "Source", "kn": "ಮೂಲ"},
    "lbl.file": {"en": "File", "kn": "ಕಡತ"},
    "lbl.type": {"en": "Type", "kn": "ಪ್ರಕಾರ"},
    "lbl.date": {"en": "Date", "kn": "ದಿನಾಂಕ"},
    "lbl.pages": {"en": "Pages", "kn": "ಪುಟಗಳು"},
    "lbl.extraction": {"en": "Extraction", "kn": "ಪಠ್ಯ ಓದುವಿಕೆ"},
    "lbl.issues": {"en": "Issues", "kn": "ಸಮಸ್ಯೆಗಳು"},
    "lbl.parties": {"en": "Parties", "kn": "ಪಕ್ಷಗಾರರು"},
    "lbl.dates": {"en": "Dates", "kn": "ದಿನಾಂಕಗಳು"},
    "lbl.identifiers": {"en": "Property identifiers", "kn": "ಸ್ವತ್ತಿನ ಗುರುತುಗಳು"},
    "lbl.effect": {"en": "Effect", "kn": "ಪರಿಣಾಮ"},
    "lbl.references": {"en": "References other documents", "kn": "ಇತರ ದಾಖಲೆಗಳ ಉಲ್ಲೇಖ"},
    "lbl.inconsistencies": {"en": "Internal inconsistencies", "kn": "ಆಂತರಿಕ ವ್ಯತ್ಯಾಸಗಳು"},
    "lbl.requiresVerification": {"en": "Requires verification", "kn": "ಪರಿಶೀಲನೆ ಅಗತ್ಯ"},
    "lbl.from": {"en": "From", "kn": "ಇವರಿಂದ"},
    "lbl.to": {"en": "To", "kn": "ಇವರಿಗೆ"},
    "lbl.transfer": {"en": "Transfer", "kn": "ವರ್ಗಾವಣೆ"},
    "lbl.document": {"en": "Document", "kn": "ದಾಖಲೆ"},
    "lbl.registration": {"en": "Registration", "kn": "ನೋಂದಣಿ"},
    "lbl.gapBefore": {"en": "gap before", "kn": "ಹಿಂದೆ ಕೊರತೆ"},
    "lbl.noTimeline": {"en": "No transfer document on record, so no ownership timeline could be constructed.",
                       "kn": "ದಾಖಲೆಯಲ್ಲಿ ವರ್ಗಾವಣೆ ದಾಖಲೆ ಇಲ್ಲದ ಕಾರಣ ಮಾಲೀಕತ್ವದ ಕಾಲಾನುಕ್ರಮ ರೂಪಿಸಲಾಗಿಲ್ಲ."},
    "lbl.consistent": {"en": "Consistent?", "kn": "ಹೊಂದಿಕೆಯೇ?"},
    "lbl.isConsistent": {"en": "Consistent", "kn": "ಹೊಂದಿಕೆಯಾಗಿದೆ"},
    "lbl.differs": {"en": "Differs", "kn": "ವ್ಯತ್ಯಾಸವಿದೆ"},
    "lbl.valuesSources": {"en": "Values and sources", "kn": "ಮೌಲ್ಯಗಳು ಮತ್ತು ಮೂಲಗಳು"},
    "lbl.notStated": {"en": "Not stated in any document.", "kn": "ಯಾವ ದಾಖಲೆಯಲ್ಲೂ ನಮೂದಿಸಿಲ್ಲ."},
    "lbl.certificate": {"en": "Certificate", "kn": "ಪ್ರಮಾಣ ಪತ್ರ"},
    "lbl.periodFrom": {"en": "Period from", "kn": "ಅವಧಿ ಪ್ರಾರಂಭ"},
    "lbl.periodTo": {"en": "Period to", "kn": "ಅವಧಿ ಅಂತ್ಯ"},
    "lbl.declaresNil": {"en": "Declares nil", "kn": "ಶೂನ್ಯ ಎಂದು ಘೋಷಿಸಿದೆ"},
    "lbl.entries": {"en": "Entries detected", "kn": "ಕಂಡುಬಂದ ನಮೂದುಗಳು"},
    "lbl.noEc": {"en": "No Encumbrance Certificate is on record.",
                 "kn": "ದಾಖಲೆಯಲ್ಲಿ ಋಣಭಾರ ಪ್ರಮಾಣ ಪತ್ರ ಇಲ್ಲ."},
    "lbl.chargeIndications": {"en": "Charge / mortgage indications", "kn": "ಅಡಮಾನ / ಬಾಧ್ಯತೆಯ ಸೂಚನೆಗಳು"},
    "lbl.ecLimitations": {"en": "Limitations of the encumbrance evidence",
                          "kn": "ಋಣಭಾರ ಸಾಕ್ಷ್ಯದ ಮಿತಿಗಳು"},
    "lbl.approvals": {"en": "Approvals on record", "kn": "ದಾಖಲೆಯಲ್ಲಿರುವ ಮಂಜೂರಾತಿಗಳು"},
    "lbl.litigationRefs": {"en": "Litigation references found in the documents",
                           "kn": "ದಾಖಲೆಗಳಲ್ಲಿ ಕಂಡುಬಂದ ವ್ಯಾಜ್ಯದ ಉಲ್ಲೇಖಗಳು"},
    "lbl.noLitigationRef": {
        "en": "No litigation reference was found in the supplied documents. This is not evidence that no litigation exists — no court record has been searched.",
        "kn": "ಸಲ್ಲಿಸಿದ ದಾಖಲೆಗಳಲ್ಲಿ ವ್ಯಾಜ್ಯದ ಯಾವುದೇ ಉಲ್ಲೇಖ ಕಂಡುಬಂದಿಲ್ಲ. ಇದು ವ್ಯಾಜ್ಯ ಇಲ್ಲವೆಂಬುದಕ್ಕೆ ಪುರಾವೆಯಲ್ಲ — ಯಾವುದೇ ನ್ಯಾಯಾಲಯ ದಾಖಲೆಯನ್ನು ಹುಡುಕಲಾಗಿಲ್ಲ.",
    },
    "lbl.restrictionRefs": {"en": "Restriction references", "kn": "ನಿರ್ಬಂಧದ ಉಲ್ಲೇಖಗಳು"},
    "lbl.checksHeading": {"en": "What was and was not checked", "kn": "ಏನನ್ನು ಪರಿಶೀಲಿಸಲಾಯಿತು, ಏನನ್ನು ಇಲ್ಲ"},
    "lbl.completed": {"en": "Completed", "kn": "ಪೂರ್ಣಗೊಂಡಿದೆ"},
    "lbl.suppliedOnly": {"en": "Performed on the supplied documents only",
                         "kn": "ಸಲ್ಲಿಸಿದ ದಾಖಲೆಗಳ ಮೇಲೆ ಮಾತ್ರ ನಡೆಸಿದ್ದು"},
    "lbl.outstanding": {"en": "Outstanding", "kn": "ಬಾಕಿ ಇರುವುದು"},
    "lbl.criticalHighHeading": {"en": "Critical and high-priority findings",
                                "kn": "ಅತಿ ಗಂಭೀರ ಮತ್ತು ಆದ್ಯತೆಯ ಅಂಶಗಳು"},
    "lbl.evidence": {"en": "Evidence", "kn": "ಸಾಕ್ಷ್ಯ"},
    "lbl.impact": {"en": "Potential impact", "kn": "ಸಂಭವನೀಯ ಪರಿಣಾಮ"},
    "lbl.requiresLegal": {"en": "Requires professional legal review.",
                          "kn": "ವೃತ್ತಿಪರ ಕಾನೂನು ಪರಿಶೀಲನೆ ಅಗತ್ಯ."},
    "lbl.confirmed": {"en": "confirmed", "kn": "ದೃಢಪಟ್ಟಿದೆ"},
    "lbl.suspected": {"en": "suspected", "kn": "ಶಂಕಿತ"},
    "lbl.confidence": {"en": "confidence", "kn": "ವಿಶ್ವಾಸ"},
    "lbl.requirement": {"en": "Requirement", "kn": "ಅಗತ್ಯ"},
    "lbl.priority": {"en": "Priority", "kn": "ಆದ್ಯತೆ"},
    "lbl.whyRequired": {"en": "Why", "kn": "ಕಾರಣ"},
    "lbl.riskIfAbsent": {"en": "Risk if absent", "kn": "ಇಲ್ಲದಿದ್ದರೆ ಅಪಾಯ"},
    "lbl.periodRelates": {"en": "Period / relates to", "kn": "ಅವಧಿ / ಸಂಬಂಧ"},
    "lbl.whereObtain": {"en": "Where to obtain it", "kn": "ಎಲ್ಲಿ ಪಡೆಯಬೇಕು"},
    "lbl.nextAction": {"en": "Next action", "kn": "ಮುಂದಿನ ಕ್ರಮ"},
    "lbl.closesWhen": {"en": "Closes when", "kn": "ಯಾವಾಗ ಮುಗಿಯುತ್ತದೆ"},
    "lbl.resolves": {"en": "Resolves", "kn": "ಪರಿಹರಿಸುತ್ತದೆ"},
    "lbl.jurisdictionCaveat": {"en": "Jurisdiction caveat.", "kn": "ವ್ಯಾಪ್ತಿಯ ಎಚ್ಚರಿಕೆ."},
    "lbl.requirementsMet": {"en": "Requirements met or closed", "kn": "ಪೂರೈಸಿದ ಅಥವಾ ಮುಕ್ತಾಯಗೊಂಡ ಅಗತ್ಯಗಳು"},
    "lbl.noQuestions": {"en": "No outstanding question arises from the current evidence.",
                        "kn": "ಪ್ರಸ್ತುತ ದಾಖಲೆಗಳಿಂದ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಉದ್ಭವಿಸುವುದಿಲ್ಲ."},
    "lbl.why": {"en": "Why", "kn": "ಕಾರಣ"},
    "lbl.group": {"en": "Group", "kn": "ಗುಂಪು"},
    "lbl.action": {"en": "Action", "kn": "ಕ್ರಮ"},
    "lbl.because": {"en": "Because", "kn": "ಕಾರಣ"},
    "lbl.dependsOn": {"en": "Depends on", "kn": "ಅವಲಂಬನೆ"},
    "lbl.riskScore": {"en": "Risk score", "kn": "ಅಪಾಯದ ಅಂಕ"},
    "lbl.indicative": {"en": "indicative", "kn": "ಸೂಚಕ"},
    "lbl.howDetermined": {"en": "How this was determined", "kn": "ಇದನ್ನು ಹೇಗೆ ನಿರ್ಧರಿಸಲಾಯಿತು"},
    "lbl.scopeLimitations": {"en": "Scope and limitations", "kn": "ವ್ಯಾಪ್ತಿ ಮತ್ತು ಮಿತಿಗಳು"},
    "lbl.disclaimer": {"en": "Disclaimer.", "kn": "ಹಕ್ಕು ನಿರಾಕರಣೆ."},
    "lbl.englishNote": {
        "en": "Shown in English: this text quotes the documents directly.",
        "kn": "ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ತೋರಿಸಲಾಗಿದೆ: ಈ ಪಠ್ಯ ದಾಖಲೆಗಳನ್ನು ನೇರವಾಗಿ ಉಲ್ಲೇಖಿಸುತ್ತದೆ.",
    },
    "lbl.ruleset": {"en": "ruleset", "kn": "ನಿಯಮಾವಳಿ"},
    "lbl.aiProcessing": {"en": "AI processing", "kn": "ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ ಪ್ರಕ್ರಿಯೆ"},
    "lbl.aiLocal": {"en": "all processing local; no document content left this machine",
                    "kn": "ಎಲ್ಲ ಪ್ರಕ್ರಿಯೆ ಸ್ಥಳೀಯ; ಯಾವುದೇ ದಾಖಲೆಯ ವಿಷಯ ಈ ಗಣಕದಿಂದ ಹೊರಹೋಗಿಲ್ಲ"},
    "lbl.aiRemote": {"en": "document text is sent to a remote provider",
                     "kn": "ದಾಖಲೆಯ ಪಠ್ಯವನ್ನು ಹೊರಗಿನ ಸೇವೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ"},
    "lbl.ocr": {"en": "OCR", "kn": "ಪಠ್ಯ ಗುರುತಿಸುವಿಕೆ"},
    "lbl.available": {"en": "available", "kn": "ಲಭ್ಯವಿದೆ"},
    "lbl.notInstalled": {"en": "not installed", "kn": "ಅಳವಡಿಸಿಲ್ಲ"},
    "lbl.jurisdictionRules": {"en": "Jurisdiction rules", "kn": "ವ್ಯಾಪ್ತಿಯ ನಿಯಮಗಳು"},
    "lbl.confirmedByPro": {"en": "confirmed by a professional", "kn": "ವೃತ್ತಿಪರರಿಂದ ದೃಢಪಟ್ಟಿದೆ"},
    "lbl.notConfirmed": {"en": "not confirmed by local counsel", "kn": "ಸ್ಥಳೀಯ ವಕೀಲರಿಂದ ದೃಢಪಟ್ಟಿಲ್ಲ"},
}

#: The Kannada disclaimer, which must read naturally rather than be assembled.
DISCLAIMER_KN = (
    "ಈ ವರದಿಯು ಪ್ರಕರಣದ ಫೋಲ್ಡರ್‌ನಲ್ಲಿ ಸಲ್ಲಿಸಿದ ದಾಖಲೆಗಳಿಂದ ಸ್ವಯಂಚಾಲಿತ ವ್ಯವಸ್ಥೆಯು ಸಿದ್ಧಪಡಿಸಿದ, "
    "ಸಾಕ್ಷ್ಯಾಧಾರಿತ ಪ್ರಾಥಮಿಕ ಮೌಲ್ಯಮಾಪನ. ಇದು ಹಕ್ಕು ತನಿಖೆಯಲ್ಲ, ಅಧಿಕೃತ ಪರಿಶೀಲನೆಯಲ್ಲ, ಕಾನೂನು "
    "ಅಭಿಪ್ರಾಯವೂ ಅಲ್ಲ. ಹಕ್ಕು ಸ್ಪಷ್ಟವಾಗಿದೆ ಅಥವಾ ಮಾರಾಟಯೋಗ್ಯ, ದಾಖಲೆ ನೈಜ, ಸ್ವತ್ತು ಋಣಭಾರ ಅಥವಾ "
    "ವ್ಯಾಜ್ಯದಿಂದ ಮುಕ್ತ, ಅಥವಾ ಖರೀದಿಗೆ ಯೋಗ್ಯ ಎಂದು ಈ ವರದಿಯ ಯಾವ ಹೇಳಿಕೆಯನ್ನೂ ಅರ್ಥೈಸಬಾರದು. "
    "ಮಹತ್ವದ ತೀರ್ಮಾನಗಳಿಗೆ ಸ್ವತಂತ್ರ ಹಕ್ಕು ತನಿಖೆ ಮತ್ತು ಅರ್ಹ ಆಸ್ತಿ ವಕೀಲರ ಲಿಖಿತ ಅಭಿಪ್ರಾಯ ಅಗತ್ಯ."
)


def rt(key: str, lang: str = "en") -> str:
    entry = REPORT_STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry["en"]


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
KANNADA_FONT_CANDIDATES = [
    "/System/Library/Fonts/NotoSansKannada.ttc",
    "/System/Library/Fonts/Supplemental/Kannada Sangam MN.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
    "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf",
]
LATIN_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


@functools.lru_cache(maxsize=1)
def kannada_font() -> Optional[str]:
    for candidate in KANNADA_FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


@functools.lru_cache(maxsize=1)
def latin_font() -> Optional[str]:
    for candidate in LATIN_FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def font_status() -> Dict[str, object]:
    return {
        "kannada_font": kannada_font(),
        "kannada_pdf_available": bool(kannada_font()),
        "note": (
            "Kannada PDFs are rendered through MuPDF's HTML engine, which shapes Kannada "
            "conjuncts correctly. ReportLab, used for English, does not shape complex scripts."
            if kannada_font() else
            "No Kannada font was found, so a Kannada PDF cannot be produced. The HTML report "
            "still renders with the reader's own fonts."
        ),
    }
