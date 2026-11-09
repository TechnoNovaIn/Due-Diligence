"""Rule-based structured extraction.

Each hit keeps the page it came from and the sentence that supports it, so
every downstream statement can cite evidence.  Values are normalised by
:mod:`app.services.normalize` - the language model is never trusted with dates,
areas or amounts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import normalize as nz
from .knowledge import SENSITIVE_TYPES

# ---------------------------------------------------------------------------
# Field vocabulary
# ---------------------------------------------------------------------------
FIELD_LABELS = {
    "Seller / Vendor / Transferor": "party_seller",
    "Buyer / Purchaser / Transferee": "party_buyer",
}

#: Human labels used in the report and the UI.
FIELD_TITLES = {
    "party_seller": "Seller / transferor",
    "party_buyer": "Purchaser / transferee",
    "party_executant": "Executant",
    "owner_name": "Owner of record",
    "previous_owner": "Previous owner",
    "party_mortgagor": "Mortgagor",
    "party_mortgagee": "Mortgagee / lender",
    "registration_number": "Registration number",
    "registration_date": "Registration date",
    "registration_office": "Registering office",
    "book_volume": "Book / volume / page",
    "document_number": "Document number",
    "execution_date": "Execution date",
    "document_date": "Document date",
    "issue_date": "Date of issue",
    "survey_number": "Survey number",
    "subdivision_number": "Subdivision / hissa number",
    "khata_number": "Khata number",
    "plot_number": "Plot number",
    "flat_number": "Flat / unit number",
    "assessment_number": "Property assessment number",
    "village": "Village",
    "hobli": "Hobli",
    "taluk": "Taluk",
    "district": "District",
    "state": "State",
    "property_area": "Extent / area",
    "built_up_area": "Built-up area",
    "uds_extent": "Undivided share (UDS)",
    "kharab_area": "Kharab area",
    "boundary_north": "Boundary - north",
    "boundary_south": "Boundary - south",
    "boundary_east": "Boundary - east",
    "boundary_west": "Boundary - west",
    "consideration_amount": "Consideration",
    "stamp_duty": "Stamp duty",
    "registration_fee": "Registration fee",
    "parent_deed_reference": "Parent / referenced document",
    "parent_registration_number": "Parent deed registration number",
    "parent_registration_date": "Parent deed registration date",
    "parent_execution_date": "Parent deed execution date",
    "adjoining_reference": "Adjoining property reference",
    "covenant_denial": "Covenant denying an encumbrance or dispute",
    "mortgage_lender": "Mortgage lender",
    "loan_amount": "Loan amount",
    "loan_account": "Loan account",
    "mortgage_status": "Mortgage status",
    "ec_period_from": "EC period - from",
    "ec_period_to": "EC period - to",
    "ec_entries": "EC entries recorded",
    "ec_nil": "EC declared nil",
    "land_classification": "Land classification",
    "conversion_order_number": "Conversion order number",
    "mutation_number": "Mutation (MR) number",
    "tax_year": "Tax period",
    "tax_amount": "Tax amount",
    "tax_receipt_number": "Tax receipt number",
    "court_case_number": "Court case reference",
    "litigation_mention": "Litigation reference",
    "approval_number": "Approval / sanction number",
    "approval_authority": "Approving authority",
    "validity_date": "Valid until",
    "rera_number": "RERA registration number",
    "identity_number": "Identity number (masked)",
    "signature_present": "Signature / seal indication",
}

NAME_KEYS = {"party_seller", "party_buyer", "party_executant", "owner_name", "previous_owner",
             "party_mortgagor", "party_mortgagee"}
DATE_KEYS = {"registration_date", "execution_date", "document_date", "ec_period_from",
             "ec_period_to", "validity_date", "issue_date"}
MONEY_KEYS = {"consideration_amount", "stamp_duty", "registration_fee", "loan_amount", "tax_amount"}
AREA_KEYS = {"property_area", "built_up_area", "uds_extent", "kharab_area"}

#: Fields whose value is a quantity. Anything captured for one of these without
#: a digit in it is prose, not a value, and is dropped rather than reported.
QUANTITY_KEYS = AREA_KEYS | {"survey_number"}

#: Recognised land classifications and tenures, English and Kannada.
_LAND_CLASS_RE = re.compile(
    r"(?:agricultur|non[\s\-]*agricultur|dry|wet|garden|bagayat|baagayat|plantation|"
    r"convert|residential|commercial|industrial|kharab|gomala|inam|patta|sarkari|"
    r"government|forest|revenue|khushki|tari|bagait|"
    "ಕ್ರಿಷಿ|ಖುಷ್ಕಿ|ತರಿ|ಬಾಗಾಯತು|ಪರಿವರ್ತನೆ|ವಸತಿ|ವಾಣಿಜ್ಯ|"
    "ಖರಾಬು|ಗೋಮಾಳ|ಇನಾಂ|ಸರ್ಕಾರಿ|ಅರಣ್ಯ)",
    re.IGNORECASE,
)

#: Latin and Kannada digits.
_DIGIT_RE = re.compile("[0-9\u0ce6-\u0cef]")


def _has_digit(text: str) -> bool:
    return bool(_DIGIT_RE.search(text or ""))
IDENTIFIER_KEYS = {"survey_number", "subdivision_number", "khata_number", "plot_number",
                   "flat_number", "assessment_number", "registration_number", "document_number",
                   "mutation_number", "conversion_order_number", "approval_number", "rera_number",
                   "court_case_number", "loan_account"}


@dataclass
class FieldHit:
    key: str
    value_raw: str
    value_norm: Optional[str] = None
    value_number: Optional[float] = None
    unit: Optional[str] = None
    page_no: Optional[int] = None
    evidence: Optional[str] = None
    confidence: float = 0.7
    extractor: str = "rules"
    provenance: str = "explicit"


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
_VAL = r"[^\n\r]{1,160}"

LABEL_PATTERNS: List[Tuple[str, str, float]] = [
    # --- registration ---
    ("registration_number", r"(?:document|doc\.?|registration|regn\.?|reg\.?)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9\-/]{2,40})", 0.85),
    ("registration_number", r"registered\s+as\s+document\s+(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9\-/]{2,40})", 0.9),
    ("registration_date", r"(?:date\s+of\s+registration|registered\s+on|registration\s+date)\s*[:\-]?\s*(" + _VAL + ")", 0.85),
    ("registration_date", r"registered\s+(?:as\s+document\s*(?:no\.?|number)?\s*[A-Za-z0-9\-/]+\s*)?(?:on|dated)\s*[:\-]?\s*(\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}[,\s]+\d{4}|\d{4}-\d{2}-\d{2})", 0.88),
    ("registration_office", r"(?:sub[\s\-]?registrar|s\.?r\.?o\.?)\s*(?:office)?\s*(?:at|of|,)?\s*[:\-]?\s*([A-Za-z .,\-]{3,60})", 0.6),
    ("book_volume", r"book\s*(?:no\.?)?\s*([IVX0-9]{1,5})\s*,?\s*volume\s*(?:no\.?)?\s*([0-9]{1,6})", 0.7),
    ("execution_date", r"(?:executed\s+on|date\s+of\s+execution|made\s+(?:and\s+executed\s+)?on\s+this|made\s+on\s+this|made\s+on)\s*[:\-]?\s*(" + _VAL + ")", 0.8),
    ("document_date", r"(?:^|\s)date\s*[:\-]\s*(\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}[,\s]+\d{4}|\d{4}-\d{2}-\d{2})", 0.75),
    ("issue_date", r"(?:certificate\s+issued\s+on|issued\s+on|date\s+of\s+issue|dated\s+this)\s*[:\-]?\s*(\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}[,\s]+\d{4}|\d{4}-\d{2}-\d{2})", 0.85),

    # --- property identifiers ---
    ("survey_number", r"(?:survey|sy\.?|s\.?)\s*(?:number|nos\.?|no\.?)\s*[:\-]?\s*([0-9]{1,5}(?:\s*/\s*[0-9A-Za-z]{1,6})*(?:\s*-\s*[0-9A-Za-z]{1,4})?)", 0.9),
    ("subdivision_number", r"(?:hissa|sub[\s\-]?division|subdivision)\s*(?:no\.?|number)\s*[:\-]?\s*([0-9A-Za-z/\-]{1,12})", 0.8),
    ("khata_number", r"(?:khata|katha|khatha)\s*(?:no\.?|number|certificate\s*no\.?)\s*[:\-]?\s*([0-9A-Za-z/\-]{1,30})", 0.85),
    ("plot_number", r"(?:plot|site)\s*(?:no\.?|number)\s*[:\-]?\s*([0-9A-Za-z/\-]{1,20})", 0.8),
    ("flat_number", r"(?:flat|apartment|unit|door)\s*(?:no\.?|number)\s*[:\-]?\s*([0-9A-Za-z/\-]{1,20})", 0.8),
    ("assessment_number", r"(?:assessment|property\s*id|pid)\s*(?:no\.?|number)?\s*[:\-]?\s*([0-9A-Za-z/\-]{3,40})", 0.75),
    ("mutation_number", r"(?:mutation|m\.?\s?r\.?)\s*(?:no\.?|number|register\s*no\.?)\s*[:\-]?\s*((?:M\.?\s?R\.?\s*)?[0-9][0-9A-Za-z/\-]{0,24})", 0.85),
    ("conversion_order_number", r"(?:conversion\s*order|order)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9/().\-]{3,60})", 0.7),
    ("rera_number", r"(?:rera\s*(?:registration)?\s*(?:no\.?|number)?\s*[:\-]?\s*)((?:PRM|ACK|PR)[A-Za-z0-9/\-]{4,40})", 0.9),
    ("approval_number", r"(?:sanction|licence|license|permit|approval|l\.?p\.?)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9/().\-]{3,50})", 0.75),
    ("court_case_number", r"\b((?:O\.?S\.?|W\.?P\.?|C\.?S\.?|R\.?S\.?A\.?|M\.?F\.?A\.?|R\.?F\.?A\.?|CRL\.?P\.?)\s*(?:No\.?)?\s*[0-9]{1,6}\s*/\s*[0-9]{2,4})", 0.85),
    ("tax_receipt_number", r"(?:receipt)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9/\-]{2,30})", 0.7),

    # --- place ---
    # Place names appear either labelled ("Village: Hosahalli") or trailing
    # ("Hosahalli Village"). A bare "Village Accountant" must not match.
    ("village", r"\bvillage\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{1,39})", 0.85),
    ("village", r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Vv]illage\b(?!\s*[:\-])", 0.8),
    ("hobli", r"\bhobli\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{1,39})", 0.85),
    ("hobli", r"\b([A-Z][a-z]+)\s+[Hh]obli\b(?!\s*[:\-])", 0.8),
    ("taluk", r"\b(?:taluka|taluk|tehsil)\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{1,39})", 0.85),
    ("taluk", r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Tt]aluk\b(?!\s*[:\-])", 0.8),
    ("district", r"\bdistrict\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{1,39})", 0.85),
    ("district", r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[Dd]istrict\b(?!\s*[:\-])", 0.8),
    ("state", r"\bstate\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{1,39})", 0.6),

    # --- boundaries ---
    ("boundary_north", r"(?:on\s+the\s+)?north\s*(?:by|:|\-)\s*(" + _VAL + ")", 0.75),
    ("boundary_south", r"(?:on\s+the\s+)?south\s*(?:by|:|\-)\s*(" + _VAL + ")", 0.75),
    ("boundary_east", r"(?:on\s+the\s+)?east\s*(?:by|:|\-)\s*(" + _VAL + ")", 0.75),
    ("boundary_west", r"(?:on\s+the\s+)?west\s*(?:by|:|\-)\s*(" + _VAL + ")", 0.75),

    # --- money ---
    ("consideration_amount", r"(?:sale\s+consideration|consideration\s+(?:amount|of)|total\s+consideration|agreed\s+(?:sale\s+)?price)\s*(?:is|of|:|\-)?\s*((?:Rs\.?|INR|₹|Rupees)[^\n\r]{1,80})", 0.85),
    ("stamp_duty", r"stamp\s+duty\s*(?:paid)?\s*(?:of|:|\-)?\s*((?:Rs\.?|INR|₹|Rupees)[^\n\r]{1,60})", 0.85),
    ("registration_fee", r"registration\s+(?:fee|charges)\s*(?:of|:|\-)?\s*((?:Rs\.?|INR|₹|Rupees)[^\n\r]{1,60})", 0.85),
    ("loan_amount", r"(?:loan|facility|credit\s+facility)\s+(?:amount\s*)?(?:of|:|\-)?\s*((?:Rs\.?|INR|₹|Rupees)[^\n\r]{1,60})", 0.8),
    ("tax_amount", r"(?:tax\s+paid|amount\s+paid|total\s+tax)\s*(?:of|:|\-)?\s*((?:Rs\.?|INR|₹|Rupees)[^\n\r]{1,60})", 0.75),
    ("loan_account", r"(?:loan\s+account|account)\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9/\-]{4,30})", 0.8),

    # --- areas ---
    ("property_area", r"(?:measuring|extent\s+of|total\s+extent|admeasuring|area\s+of|extent)\s*[:\-]?\s*([^\n\r]{1,70})", 0.8),
    ("built_up_area", r"(?:built[\s\-]?up\s+area|super\s+built[\s\-]?up\s+area|plinth\s+area)\s*[:\-]?\s*([^\n\r]{1,60})", 0.85),
    ("uds_extent", r"(?:undivided\s+share|uds)\s*(?:of\s+land)?\s*(?:of|:|\-|measuring)?\s*([^\n\r]{1,60})", 0.8),
    ("kharab_area", r"kharab\s*(?:area)?\s*[:\-]?\s*([^\n\r]{1,40})", 0.8),

    # --- land record ---
    ("land_classification", r"(?:classification|land\s+(?:use|type)|nature\s+of\s+land)\s*[:\-]?\s*([A-Za-z \-/]{3,50})", 0.7),
    ("owner_name", r"(?:name\s+of\s+the\s+(?:owner|holder|khatedar)|standing\s+in\s+the\s+name\s+of|khatedar|assessee)\s*[:\-]?\s*([A-Za-z][A-Za-z .'\-]{2,59})", 0.8),
    ("owner_name", r"(?:^|\s)(?:owner|holder)\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{2,59})", 0.75),
    ("tax_year", r"(?:financial\s+year|for\s+the\s+year|period|assessment\s+year)\s*[:\-]?\s*(\d{4}\s*[\-/]\s*\d{2,4})", 0.8),

    # --- EC ---
    ("ec_period_from", r"period\s+from\s*[:\-]?\s*([0-9]{1,2}[\-/.][0-9]{1,2}[\-/.][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})", 0.9),
    ("ec_period_to", r"(?:to|till|up\s*to|until)\s*[:\-]?\s*([0-9]{1,2}[\-/.][0-9]{1,2}[\-/.][0-9]{2,4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})", 0.6),

    # --- approvals ---
    ("approval_authority", r"(?:issued\s+by|sanctioned\s+by|approved\s+by|competent\s+authority)\s*[:\-]?\s*([A-Za-z .,'\-&()]{4,80})", 0.7),
    ("validity_date", r"(?:valid\s+(?:up\s*to|until|till)|validity)\s*[:\-]?\s*(" + _VAL + ")", 0.75),
]

#: Narrative party patterns - deeds name parties in prose, not in labelled fields.
PARTY_PATTERNS: List[Tuple[str, str, float]] = [
    ("party_seller", r"(?:vendor|seller|transferor)\s*[:\-]\s*([A-Za-z .'\-]{3,60})", 0.85),
    ("party_buyer", r"(?:purchaser|buyer|transferee)\s*[:\-]\s*([A-Za-z .'\-]{3,60})", 0.85),
    ("party_mortgagor", r"(?:mortgagor)\s*[:\-]\s*([A-Za-z .'\-]{3,60})", 0.85),
    ("party_mortgagee", r"(?:mortgagee|lender|bank)\s*[:\-]\s*([A-Za-z .,'\-&]{3,80})", 0.75),
    ("party_donor", r"(?:donor)\s*[:\-]\s*([A-Za-z .'\-]{3,60})", 0.85),
]

#: References to other documents that must therefore exist.
PARENT_DEED_PATTERNS = [
    r"(?:by\s+virtue\s+of|acquired\s+(?:the\s+)?(?:said\s+)?property\s+(?:under|through|by)|derived\s+title\s+(?:under|from)|under\s+(?:a|the)\s+registered)\s+([^\n\r.;]{5,160})",
    r"(?:partition\s+deed|sale\s+deed|gift\s+deed|settlement\s+deed|release\s+deed|will|decree|mother\s+deed|parent\s+document)\s+(?:dated|bearing|registered)\s+([^\n\r.;]{3,140})",
]

MORTGAGE_SIGNALS = [
    (r"\b(?:mortgag\w*|hypotheca\w*|charge\s+created|charge\s+over|deposit\s+of\s+title\s+deeds|"
     # "encumbered" asserts a charge; the noun "encumbrance" is just the name of
     # the certificate, so it is deliberately not a signal.
     r"equitable\s+mortgage|lien|liens|encumbered)\b", "mortgage_indicated"),
    (r"\b(?:loan\s+(?:sanction\w*|availed|outstanding)|housing\s+loan|term\s+loan|"
     r"sanctioned\s+a\s+loan)\b", "loan_indicated"),
]
MORTGAGE_RELEASE_SIGNALS = [
    r"\b(?:loan\s+(?:closed|closure|repaid|fully\s+repaid|account\s+closed)"
    r"|mortgage\s+(?:released|discharged|satisfied)|release\s+of\s+mortgage|reconvey\w*"
    r"|charge\s+satisfied|discharge\s+of\s+mortgage"
    # "no dues" only counts when it is about the loan, not about property tax.
    r"|no\s+dues\s+(?:certificate|in\s+respect\s+of\s+the\s+loan)"
    r"|(?:loan|mortgage|charge)[^.\n]{0,40}?nil\s+outstanding)\b"
]
LITIGATION_SIGNALS = [
    (r"\b(?:stay\s+order|interim\s+order|injunction)\b", "injunction"),
    (r"\b(?:suit\s+(?:is\s+)?pending|pending\s+(?:suit|litigation|proceeding\w*)|"
     r"sub[\s\-]?judice|litigation)\b", "pending_litigation"),
    (r"\b(?:land\s+acquisition|preliminary\s+notification|section\s+4\(1\)|acquisition\s+proceedings)\b", "acquisition"),
    (r"\b(?:attachment|prohibitory\s+order|attached\s+by)\b", "attachment"),
    (r"\b(?:caveat|legal\s+notice|dispute\s+between)\b", "dispute_reference"),
    (r"\b(?:decree|judgment|decreed|dismissed)\b", "court_decision"),
]
RESTRICTION_SIGNALS = [
    (r"\b(?:shall\s+not\s+alienate|restriction\s+on\s+(?:transfer|alienation)|non[\s\-]?alienable|cannot\s+be\s+(?:sold|transferred)|prior\s+permission\s+(?:of|from))\b", "transfer_restriction"),
    (r"\b(?:granted\s+land|darkhast|inam|ptcl|scheduled\s+caste|scheduled\s+tribe\s+grant)\b", "grant_land_indicator"),
    (r"\b(?:tenancy|tenant|occupancy\s+rights|form\s+no\.?\s*7)\b", "tenancy_indicator"),
]
EC_NIL_PATTERNS = [r"\bno\s+encumbrance\b", r"\bnil\s+encumbrance\b", r"\bnil\b\s*$", r"no\s+entries?\s+(?:were\s+)?found"]
SIGNATURE_PATTERNS = [r"\b(?:sd/-|signature\s+of|signed\s+and\s+delivered|witness(?:es)?\s*[:\-]|seal\s+of|in\s+the\s+presence\s+of)\b"]
MISSING_PAGE_PATTERNS = [r"page\s+(\d{1,3})\s+of\s+(\d{1,3})"]


# ---------------------------------------------------------------------------
# Kannada patterns
# ---------------------------------------------------------------------------
# Karnataka's own records - Bhoomi RTC/Pahani, Kaveri encumbrance certificates,
# panchayat khata extracts and most registered deeds - are written in Kannada.
# These patterns mirror the English ones above.
#
# Two things differ from the English patterns and matter:
#   * a trailing \b is unusable after a Kannada word, because vowel signs and the
#     anusvara are combining marks and therefore not word characters;
#   * values may contain Kannada letters, so the value class includes U+0C80-U+0CFF.
#
# These terms follow common Karnataka revenue and registration usage; they should
# be reviewed by a Kannada-speaking property professional before the output is
# relied on.

#: Kannada *letters* only. The Kannada block carries its own digits at
#: U+0CE6-U+0CEF; including them in a name or place class makes "೨೦೨೪" match as a
#: village name. They are excluded here and allowed only inside identifiers.
_KN_L = "\\u0C80-\\u0CE5\\u0CF1-\\u0CFF"
#: A value that may be written in Kannada, Latin or both.
_KN_VAL = r"[^\n\r]{1,160}"
#: A name-like value: Kannada letters, Latin letters, spaces and the usual punctuation.
_KN_NAME = "[" + _KN_L + "A-Za-z][" + _KN_L + "A-Za-z .\\u200c\\u200d'\\-]{1,79}"
#: A place name: as above but shorter, and never swallowing the next label.
_KN_PLACE = "[" + _KN_L + "A-Za-z][" + _KN_L + "A-Za-z .\\u200c\\u200d'\\-]{1,39}"
#: An identifier: digits, Latin and Kannada letters, and the zero-width joiners that
#: Kannada transliterations of Latin abbreviations carry ("ಕೆಎ-ಬಿಎನ್‌ಜಿ-4521/2015").
_KN_ID = ("[0-9A-Za-z\\u0C80-\\u0CFF]"
          "[0-9A-Za-z\\u0C80-\\u0CFF\\u200c\\u200d/\\-]{0,39}")
_KN_DATE = (r"\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}"
            "|\\d{1,2}\\s*(?:ನೇ|ನೆ)?\\s*[" + _KN_L + "]{2,12}\\s*,?\\s*\\d{4}"
            r"|\d{4}-\d{2}-\d{2}")
_KN_MONEY = r"(?:ರೂ\.?|ರೂಪಾಯಿ(?:ಗಳು)?|Rs\.?|₹)[^\n\r]{1,60}"

KANNADA_LABEL_PATTERNS: List[Tuple[str, str, float]] = [
    # --- property identifiers ---
    ("survey_number", r"(?:ಸರ್ವೇ|ಸರ್ವೆ|ಸ\.ನಂ\.?)\s*(?:ಸಂಖ್ಯೆ|ನಂಬರ್|ನಂ\.?)?\s*[:\-]?\s*"
     # "96/1,2" is one parcel reference covering two hissas, not the number 96/1
     # followed by stray punctuation.
     r"(" + _KN_ID + r"(?:\s*,\s*\d+(?:/\d+)?)*)", 0.9),
    ("subdivision_number", r"ಹಿಸ್ಸಾ\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)?\s*[:\-]?\s*(" + _KN_ID + ")", 0.85),
    ("khata_number", r"(?:ಖಾತಾ|ಖಾತೆ)\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.85),
    ("plot_number", r"(?:ನಿವೇಶನ|ಪ್ಲಾಟ್)\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.8),
    ("flat_number", r"(?:ಫ್ಲಾಟ್|ಮನೆ)\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.8),
    ("assessment_number", r"ನಿರ್ಧಾರಣ\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.75),
    # The number is often written after an "M.R." prefix rather than straight after the label.
    ("mutation_number",
     "(?:ಮ್ಯುಟೇಶನ್|ಮ್ಯೂಟೇಶನ್|ವರ್ಗಾವಣೆ|ಎಂ\\.?\\s?ಆರ್\\.?)\\s*(?:ಸಂಖ್ಯೆ|ನಂ\\.?)\\s*[:\\-]?\\s*"
     "((?:ಎಂ\\.?\\s?ಆರ್\\.?\\s*)?[0-9][0-9A-Za-z/\\-]{0,24})", 0.85),
    ("registration_number", r"(?:ನೋಂದಣಿ|ದಸ್ತಾವೇಜು|ದಾಖಲೆ)\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.88),
    ("approval_number", r"(?:ಆದೇಶ|ಮಂಜೂರಾತಿ|ಪರವಾನಗಿ)\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.75),
    ("tax_receipt_number", r"ರಸೀದಿ\s*(?:ಸಂಖ್ಯೆ|ನಂ\.?)\s*[:\-]?\s*(" + _KN_ID + ")", 0.75),

    # --- place ---
    ("village", r"ಗ್ರಾಮ(?![\u0C80-\u0CFF])(?!\s*ಪಂಪ್ಯ|\s*ಪಂಚಾಯ|\s*ಪಣಂತಾಯ|\s*ಪಂಚಾಯಿ)\s*[:\-]\s*(" + _KN_PLACE + ")", 0.85),
    ("hobli", r"ಹೋಬಳಿ\s*[:\-]\s*(" + _KN_PLACE + ")", 0.85),
    ("taluk", r"(?:ತಾಲ್ಲೂಕು|ತಾಲೂಕು|ತಾಲ್ಲೂಕ)\s*[:\-]\s*(" + _KN_PLACE + ")", 0.85),
    ("district", r"ಜಿಲ್ಲೆ\s*[:\-]\s*(" + _KN_PLACE + ")", 0.85),
    # Trailing form: "ಹೊಸಹಳ್ಳಿ ಗ್ರಾಮ", "ನೆಲಮಂಗಲ ತಾಲ್ಲೂಕು"
    ("village", "([" + _KN_L + "]{2,20})\\s+ಗ್ರಾಮ(?![\u0C80-\u0CFF])(?!\\s*ಪಂಪ್ಯ|\\s*ಪಂಚಾಯ|\\s*ಪಣಂತಾಯ|\\s*ಪಂಚಾಯಿ)(?![\\s]*[:\\-])", 0.8),
    ("taluk", "([" + _KN_L + "]{2,20})\\s+(?:ತಾಲ್ಲೂಕು|ತಾಲೂಕು)(?![\u0C80-\u0CFF])(?![\\s]*[:\\-])", 0.8),
    ("district", "([" + _KN_L + "]{2,25}(?:\\s+[" + _KN_L + "]{2,15})?)\\s+ಜಿಲ್ಲೆ(?![\u0C80-\u0CFF])(?![\\s]*[:\\-])", 0.8),
    ("hobli", "([" + _KN_L + "]{2,20})\\s+ಹೋಬಳಿ(?![\u0C80-\u0CFF])(?![\\s]*[:\\-])", 0.8),

    # --- parties ---
    # A Karnataka deed introduces each party as "<name> - <age> ವರ್ಷ, ಬಿನ್ <father>".
    # The Kaveri cover sheet that carries the seller/buyer labels is a stamped form
    # that often scans badly, so this block in the body is frequently the only place
    # the names can be read at all. The role is deliberately not guessed.
    ("party_executant", "([" + _KN_L + "A-Za-z][" + _KN_L + "A-Za-z.\\u200c\\u200d]{2,39})\\s*[-\u2014\u2013]\\s*\\d{1,3}\\s*\u0cb5\u0cb0\u0ccd\u0cb7", 0.8),
    # The registration sheet's own wording for the two sides of a sale.
    ("party_buyer", r"\u0c95\u0ccd\u0cb0\u0caf\u0c95\u0ccd\u0c95\u0cc6\s*\u0caa\u0ca1\u0cc6\u0caf\u0cc1\u0cb5\u0cb5\u0cb0\s*\u0cb9\u0cc6\u0cb8\u0cb0\u0cc1\s*[:\-]?\s*(" + _KN_NAME + ")", 0.8),
    ("party_seller", r"\u0c95\u0ccd\u0cb0\u0caf\u0c95\u0ccd\u0c95\u0cc6\s*\u0c95\u0ccb\u0ca1\u0cc1\u0cb5\u0cb5\u0cb0\s*\u0cb9\u0cc6\u0cb8\u0cb0\u0cc1\s*[:\-]?\s*(" + _KN_NAME + ")", 0.8),
    ("party_seller", r"(?:ಮಾರಾಟಗಾರ(?:ರು)?|ವಿಕ್ರಯದಾರ(?:ರು)?|ಮಾರಿಕೊಟ್ಟವರು)\s*[:\-]\s*(" + _KN_NAME + ")", 0.88),
    ("party_buyer", r"(?:ಖರೀದಿದಾರ(?:ರು)?|ಕ್ರಯದಾರ(?:ರು)?|ಕೊಂಡುಕೊಂಡವರು)\s*[:\-]\s*(" + _KN_NAME + ")", 0.88),
    ("party_mortgagor", r"ಅಡಮಾನದಾರ(?:ರು)?\s*[:\-]\s*(" + _KN_NAME + ")", 0.88),
    ("party_mortgagee", r"(?:ಅಡಮಾನ\s*ಸ್ವೀಕರಿಸಿದವರು|ಸಾಲ\s*ನೀಡಿದವರು)\s*[:\-]\s*(" + _KN_NAME + ")", 0.85),
    ("owner_name", r"(?:ಖಾತೆದಾರ(?:ರ)?(?:\s*ಹೆಸರು)?|ಮಾಲೀಕ(?:ರ)?(?:\s*ಹೆಸರು)?)\s*[:\-]\s*(" + _KN_NAME + ")", 0.85),

    # --- areas ---
    ("property_area", r"(?:ಒಟ್ಟು\s*)?(?:ವಿಸ್ತೀರ್ಣ|ಅಳತೆ)\s*[:\-]?\s*(" + _KN_VAL + ")", 0.85),
    ("kharab_area", r"ಖರಾಬು\s*[:\-]?\s*([^\n\r]{1,40})", 0.85),
    ("built_up_area", r"ಕಟ್ಟಡ\s*ವಿಸ್ತೀರ್ಣ\s*[:\-]?\s*([^\n\r]{1,60})", 0.85),
    ("uds_extent", r"ಅವಿಭಜಿತ\s*ಪಾಲು\s*[:\-]?\s*([^\n\r]{1,60})", 0.8),

    # --- money ---
    ("consideration_amount", r"(?:ಕ್ರಯದ\s*ಮೊತ್ತ|ಪ್ರತಿಫಲ|ಮಾರಾಟದ\s*ಮೊತ್ತ)\s*[:\-]?\s*(" + _KN_MONEY + ")", 0.88),
    ("loan_amount", r"ಸಾಲ(?:ದ)?\s*(?:ಮೊತ್ತ)?\s*[:\-]?\s*(" + _KN_MONEY + ")", 0.8),
    ("tax_amount", r"(?:ಪಾವತಿಸಿದ\s*ಮೊತ್ತ|ತೆರಿಗೆ\s*ಮೊತ್ತ)\s*[:\-]?\s*(" + _KN_MONEY + ")", 0.8),
    ("stamp_duty", r"ಮುದ್ರಾಂಕ\s*ಶುಲ್ಕ\s*[:\-]?\s*(" + _KN_MONEY + ")", 0.85),

    # --- dates ---
    ("document_date", r"ದಿನಾಂಕ\s*[:\-]\s*(" + _KN_DATE + ")", 0.8),
    ("registration_date", r"ನೋಂದಣಿ\s*ದಿನಾಂಕ\s*[:\-]?\s*(" + _KN_DATE + ")", 0.88),
    ("issue_date", r"(?:ನೀಡಿದ\s*ದಿನಾಂಕ|ವಿತರಿಸಿದ\s*ದಿನಾಂಕ)\s*[:\-]?\s*(" + _KN_DATE + ")", 0.85),
    ("validity_date", r"(?:ಮಾನ್ಯತೆ|ಊರ್ಜಿತ)\s*(?:ಅವಧಿ)?\s*[:\-]?\s*(" + _KN_DATE + ")", 0.75),
    ("tax_year", r"ಆರ್ಥಿಕ\s*ವರ್ಷ\s*[:\-]?\s*(\d{4}\s*[\-/]\s*\d{2,4})", 0.85),

    # --- boundaries ---
    ("boundary_north", r"ಉತ್ತರ(?:ಕ್ಕೆ|ದಿಕ್ಕಿಗೆ)?\s*[:\-]\s*(" + _KN_VAL + ")", 0.8),
    ("boundary_south", r"ದಕ್ಷಿಣ(?:ಕ್ಕೆ|ದಿಕ್ಕಿಗೆ)?\s*[:\-]\s*(" + _KN_VAL + ")", 0.8),
    ("boundary_east", r"ಪೂರ್ವ(?:ಕ್ಕೆ|ದಿಕ್ಕಿಗೆ)?\s*[:\-]\s*(" + _KN_VAL + ")", 0.8),
    ("boundary_west", r"ಪಶ್ಚಿಮ(?:ಕ್ಕೆ|ದಿಕ್ಕಿಗೆ)?\s*[:\-]\s*(" + _KN_VAL + ")", 0.8),

    # --- land record ---
    ("land_classification", r"(?:ಜಮೀನಿನ\s*ವರ್ಗ|ಭೂಮಿಯ\s*ವರ್ಗ|ವರ್ಗೀಕರಣ)\s*[:\-]?\s*([^\n\r]{2,50})", 0.75),
    ("approval_authority", r"(?:ನೀಡಿದವರು|ಮಂಜೂರು\s*ಮಾಡಿದವರು|ಸಕ್ಷಮ\s*ಪ್ರಾಧಿಕಾರ)\s*[:\-]?\s*([^\n\r]{3,80})", 0.7),
]

#: Kannada boundary markers, for the "neighbouring property" check.
_KN_DIRECTION_RE = re.compile(r"(?:ಉತ್ತರ|ದಕ್ಷಿಣ|ಪೂರ್ವ|ಪಶ್ಚಿಮ)(?:ಕ್ಕೆ|ದಿಕ್ಕಿಗೆ)?\s*[:\-]")

#: Kannada equivalents of the signal vocabulary.
KANNADA_MORTGAGE_SIGNALS = [
    # ಋಣಭಾರ ("encumbrance") is the name of the certificate itself and is therefore
    # not a signal; ಅಡಮಾನ ("mortgage") and ಗಿರವಿ ("pledge") assert a charge.
    (r"(?:ಅಡಮಾನ|ಗಿರವಿ|ಋಣ\s*ಸೃಷ್ಟಿ|ಬಾಧ್ಯತೆ\s*ಸೃಷ್ಟಿ)", "mortgage_indicated"),
    (r"(?:ಸಾಲ\s*ಮಂಜೂರು|ಸಾಲದ\s*ಮೊತ್ತ|ಗೃಹ\s*ಸಾಲ|ಬ್ಯಾಂಕ್\s*ಸಾಲ)", "loan_indicated"),
]
KANNADA_MORTGAGE_RELEASE_SIGNALS = [
    # ಬಾಕಿ ಇಲ್ಲ ("no dues") appears on every tax receipt, so it must be tied to the
    # loan or the charge before it counts as a discharge.
    r"(?:ಅಡಮಾನ\s*ಬಿಡುಗಡೆ|ಅಡಮಾನ\s*ವಿಮೋಚನೆ|ಸಾಲ\s*ಮುಕ್ತಾಯ|ಸಾಲ\s*ಮರುಪಾವತಿ"
    r"|ಋಣ\s*ವಿಮೋಚನೆ|ಸಾಲ(?:ದ)?\s*ಬಾಕಿ\s*ಇಲ್ಲ|ಸಾಲ\s*ಖಾತೆ\s*ಮುಕ್ತಾಯ)"
]
KANNADA_LITIGATION_SIGNALS = [
    (r"(?:ತಡೆಯಾಜ್ಞೆ|ತಾತ್ಕಾಲಿಕ\s*ಆದೇಶ|ನಿಷೇಧಾಜ್ಞೆ)", "injunction"),
    (r"(?:ಬಾಕಿ\s*ಇರುವ\s*ದಾವೆ|ವ್ಯಾಜ್ಯ|ದಾವೆ\s*ಬಾಕಿ|ಪ್ರಕರಣ\s*ಬಾಕಿ)", "pending_litigation"),
    (r"(?:ಭೂ\s*ಸ್ವಾಧೀನ|ಪ್ರಾಥಮಿಕ\s*ಅಧಿಸೂಚನೆ|ಸ್ವಾಧೀನ\s*ಪ್ರಕ್ರಿಯೆ)", "acquisition"),
    (r"(?:ಜಪ್ತಿ|ಮುಟ್ಟುಗೋಲು|ನಿಷೇಧಕ\s*ಆದೇಶ)", "attachment"),
    (r"(?:ಕೆವಿಯಟ್|ಕಾನೂನು\s*ನೋಟೀಸು|ವಿವಾದ)", "dispute_reference"),
    (r"(?:ಡಿಕ್ರಿ|ತೀರ್ಪು|ವಜಾ)", "court_decision"),
]
KANNADA_RESTRICTION_SIGNALS = [
    (r"(?:ಪರಭಾರೆ\s*ಮಾಡುವಂತಿಲ್ಲ|ವರ್ಗಾವಣೆ\s*ನಿರ್ಬಂಧ|ಮಾರಾಟ\s*ಮಾಡುವಂತಿಲ್ಲ|ಪೂರ್ವಾನುಮತಿ)", "transfer_restriction"),
    (r"(?:ಮಂಜೂರಾದ\s*ಭೂಮಿ|ದರಖಾಸ್ತು|ಇನಾಮು|ಪಿ\.ಟಿ\.ಸಿ\.ಎಲ್|ಪರಿಶಿಷ್ಟ\s*ಜಾತಿ)", "grant_land_indicator"),
    (r"(?:ಗೇಣಿದಾರ|ಗೇಣಿ|ಒಕ್ಕಲುತನ)", "tenancy_indicator"),
]
#: Covenants that deny an encumbrance rather than disclose one.
KANNADA_NEGATION_RE = re.compile(
    r"(?:ಯಾವುದೇ\s*(?:ಋಣ|ಅಡಮಾನ|ವ್ಯಾಜ್ಯ|ಬಾಧ್ಯತೆ)[^\n]{0,24}?ಇಲ್ಲ"
    r"|ಋಣಭಾರ\s*ರಹಿತ|ಮುಕ್ತವಾಗಿ(?:ದೆ|ರುತ್ತದೆ)|ಯಾವುದೇ\s*ನಮೂದು\s*ಇಲ್ಲ|ನಿರಪೇಕ್ಷ)"
)
KANNADA_EC_NIL_PATTERNS = [r"ಯಾವುದೇ\s*ಋಣಭಾರ\s*ಇಲ್ಲ", r"ಯಾವುದೇ\s*ನಮೂದು\s*ಇಲ್ಲ", r"ಶೂನ್ಯ"]
#: EC period: "ಅವಧಿ: 01/04/2019 ರಿಂದ 30/06/2024 ವರೆಗೆ"
KANNADA_EC_PERIOD_RE = re.compile(
    r"ಅವಧಿ\s*[:\-]?\s*(" + _KN_DATE + r")\s*ರಿಂದ\s*(" + _KN_DATE + r")\s*(?:ವರೆಗೆ)?"
)
#: Recitals pointing at an earlier deed.
KANNADA_RECITAL_RE = re.compile(
    r"(?:ಮೂಲಕ\s*ಹಕ್ಕು|ಪೂರ್ವದ\s*ದಾಖಲೆ|ಮೂಲ\s*ಪತ್ರ|ಹಿಂದಿನ\s*ಕ್ರಯ|ಅನ್ವಯ\s*ಹಕ್ಕು\s*ಪಡೆದು)")
KANNADA_PARENT_DEED_PATTERNS = [
    r"(?:ಪಾಲು\s*ಪತ್ರ|ಕ್ರಯ\s*ಪತ್ರ|ದಾನ\s*ಪತ್ರ|ಸಂಧಾನ\s*ಪತ್ರ|ಬಿಡುಗಡೆ\s*ಪತ್ರ|ಉಯಿಲು|ಡಿಕ್ರಿ|ಮೂಲ\s*ಪತ್ರ)"
    r"\s*(?:ದಿನಾಂಕ|ಸಂಖ್ಯೆ)[^\n\r]{3,120}",
]
KANNADA_SIGNATURE_PATTERNS = [r"(?:ಸಹಿ|ಸಾಕ್ಷಿ(?:ದಾರರು)?|ಮುದ್ರೆ|ಇವರ\s*ಸಮಕ್ಷಮ)"]


_DIRECTION_RE = re.compile(r"\b(?:north|south|east|west)\b\s*(?:by|:|\-)", re.IGNORECASE)

# Both scripts are scanned on every document: a Karnataka file routinely mixes a
# Kannada RTC with an English sale deed, and some documents are bilingual.
ALL_LABEL_PATTERNS = LABEL_PATTERNS + KANNADA_LABEL_PATTERNS
ALL_MORTGAGE_SIGNALS = MORTGAGE_SIGNALS + KANNADA_MORTGAGE_SIGNALS
ALL_MORTGAGE_RELEASE_SIGNALS = MORTGAGE_RELEASE_SIGNALS + KANNADA_MORTGAGE_RELEASE_SIGNALS
ALL_LITIGATION_SIGNALS = LITIGATION_SIGNALS + KANNADA_LITIGATION_SIGNALS
ALL_RESTRICTION_SIGNALS = RESTRICTION_SIGNALS + KANNADA_RESTRICTION_SIGNALS
ALL_SIGNATURE_PATTERNS = SIGNATURE_PATTERNS + KANNADA_SIGNATURE_PATTERNS
ALL_PARENT_DEED_PATTERNS = PARENT_DEED_PATTERNS + KANNADA_PARENT_DEED_PATTERNS


def _evidence(line: str, limit: int = 300) -> str:
    return nz.clean_text(line)[:limit]


#: A covenant that *denies* an encumbrance or dispute must not be read as one.
_NEGATION_RE = re.compile(
    r"(?:free\s+from|free\s+of|not\s+subject\s+to|without\s+any|no\s+subsisting|"
    r"there\s+(?:is|are)\s+no|nil|never\s+been|unencumbered|clear\s+of)\b",
    re.IGNORECASE,
)


def _is_negated(line: str, position: int) -> bool:
    """True when the signal sits inside a denial such as `free from ... litigation`.

    Kannada puts the negation *after* the noun ("ಯಾವುದೇ ಋಣಭಾರ ಇಲ್ಲ"), so the window
    extends both ways for that script.
    """
    before = line[max(0, position - 120):position]
    if _NEGATION_RE.search(before):
        return True
    around = line[max(0, position - 60):position + 120]
    return bool(KANNADA_NEGATION_RE.search(around))


#: Labels that terminate a place value captured from a multi-column line such as
#: "Village: Hosahalli    Hobli: Kasaba    Taluk: Nelamangala".
_PLACE_STOP_RE = re.compile(
    r"\b(?:village|hobli|taluk|taluka|tehsil|district|state|survey|hissa|khata|katha|year|"
    r"extent|classification|name|block|panchayat|address)\b"
    # Kannada labels: a trailing \b is unusable (these end in combining marks), and a
    # lookahead is required so ಗ್ರಾಮ does not match inside ಗ್ರಾಮಾಂತರ or ಗ್ರಾಮೀಣ.
    # Kannada records lay labels out in columns on one line, so a captured value
    # runs on into the next label unless it is cut here.
    # Column labels that sit beside a place name on the same line. "ತುಮಕೂರು ಬ್ಲಾಕ್"
    # ("Tumkur block") was being reported as a district conflicting with "ತುಮಕೂರು".
    r"|(?:ಗ್ರಾಮ|ಹೋಬಳಿ|ತಾಲ್ಲೂಕು|ತಾಲೂಕು|ಜಿಲ್ಲೆ|ರಾಜ್ಯ|ಸರ್ವೇ|ಸರ್ವೆ|ಹಿಸ್ಸಾ|ಖಾತಾ|ಖಾತೆ|ಖಾತೆದಾರ"
    r"|ಬ್ಲಾಕ್|ಪಂಚಾಯತಿ|ಪಂಚಾಯಿತಿ|ಪಣಂತಾಯತಿ|ನಗರ|ಪುರಸಭೆ|ವಿಳಾಸ|ವಯಸ್ಸು"
    r"|ವಿಸ್ತೀರ್ಣ|ಅಳತೆ|ಖರಾಬು|ದಿನಾಂಕ|ಬೆಳೆ|ವರ್ಷ|ಸಂಖ್ಯೆ|ನಂ|ಮಾಲೀಕ|ಹೆಸರು|ವರ್ಗ|ಕಂದಾಯ"
    r"|ಮ್ಯುಟೇಶನ್|ವರ್ಗಾವಣೆ|ಅವಧಿ|ರಸೀದಿ|ಮೊತ್ತ)"
    r"(?![\u0C80-\u0CFF])",
    re.IGNORECASE,
)

_PLACE_KEYS = {"village", "hobli", "taluk", "district", "state"}

#: Recitals describing how the transferor acquired the property. A registration
#: number quoted inside one belongs to the *parent* deed, not to this document.
_RECITAL_RE = re.compile(
    r"(?:by\s+virtue\s+of|acquired\s+the\s+said|derived\s+title|under\s+(?:a|the)\s+registered|"
    r"predecessor\s+in\s+title|earlier\s+title|parent\s+(?:deed|document)|mother\s+deed)",
    re.IGNORECASE,
)


def _truncate_place(value: str) -> str:
    m = _PLACE_STOP_RE.search(value)
    if m:
        value = value[: m.start()]
    return value.strip(" .,;:-")


def _truncate_boundary(value: str) -> str:
    """A boundary clause ends where the next direction begins, in either script."""
    starts = [m.start() for m in (_DIRECTION_RE.search(value), _KN_DIRECTION_RE.search(value))
              if m is not None]
    if starts:
        value = value[: min(starts)]
    return value.strip(" .,;:-")


def _in_boundary_context(line: str, position: int) -> bool:
    """True when the match sits inside a boundary clause (`North by Sy No 122`)."""
    prefix = line[:position]
    last_end = None
    for rx in (_DIRECTION_RE, _KN_DIRECTION_RE):
        for m in rx.finditer(prefix):
            last_end = m.end() if last_end is None else max(last_end, m.end())
    return last_end is not None and (position - last_end) < 60


def _iter_lines(pages) -> Iterable[Tuple[int, str]]:
    for page in pages:
        for line in (page.text or "").splitlines():
            if line.strip():
                yield page.page_no, line


def _page_blobs(pages) -> Iterable[Tuple[int, str]]:
    for page in pages:
        yield page.page_no, page.text or ""


# ---------------------------------------------------------------------------
class _DigitNormalisedPage:
    """A page whose Indic digits have been mapped to ASCII.

    Kannada records are written with Kannada digits (U+0CE6-U+0CEF), which no
    ``\\d`` pattern matches. The mapping is one character to one character, so
    page offsets - and therefore the page and evidence attached to every hit -
    are unchanged.
    """

    __slots__ = ("page_no", "text", "ocr_used", "confidence")

    def __init__(self, page: Any) -> None:
        self.page_no = page.page_no
        self.text = nz.westernize_digits(page.text or "")
        self.ocr_used = getattr(page, "ocr_used", False)
        self.confidence = getattr(page, "confidence", 1.0)

    @property
    def char_count(self) -> int:
        return len(self.text)


def extract_fields(pages: Sequence[Any], doc_type: str = "unknown") -> List[FieldHit]:
    """Run every applicable pattern over the document and return evidence-bound hits."""
    pages = [_DigitNormalisedPage(page) for page in pages]
    hits: List[FieldHit] = []
    seen: set = set()

    def add(hit: Optional[FieldHit]) -> None:
        if hit is None:
            return
        value = (hit.value_norm or hit.value_raw or "").strip().lower()
        if not value or len(value) < 1:
            return
        if hit.key == "land_classification" and not _LAND_CLASS_RE.search(hit.value_raw or ""):
            # Anything may follow the word "classification" on a scanned plan.
            # A classification is one of a known set of tenures and land uses, so
            # a value that names none of them is a caption, not a classification.
            return
        if hit.key in QUANTITY_KEYS and not _has_digit(hit.value_raw or ""):
            # An extent or a price with no digit in it is not a low-confidence
            # reading of one, it is the label pattern having run on into prose.
            # Common on OCR'd pages, where the value is often lost but the
            # surrounding sentence is not.
            return
        sig = (hit.key, value)
        if sig in seen:
            return
        seen.add(sig)
        hits.append(hit)

    sensitive = doc_type in SENSITIVE_TYPES

    previous_line = ""
    for page_no, line in _iter_lines(pages):
        # A covenant frequently wraps across a line break, so the negation check
        # looks at the preceding line as well.
        context = (previous_line + " " + line) if previous_line else line
        offset = len(previous_line) + 1 if previous_line else 0
        previous_line = line
        lower = line.lower()
        for key, pattern, conf in ALL_LABEL_PATTERNS:
            for m in re.finditer(pattern, line, re.IGNORECASE):
                raw = nz.clean_text(m.group(1))
                if not raw:
                    continue
                if key.startswith("boundary_"):
                    raw = _truncate_boundary(raw)
                    if not raw:
                        continue
                elif key in _PLACE_KEYS:
                    raw = _truncate_place(raw)
                    if len(raw) < 2:
                        continue
                elif key in ("registration_number", "registration_date", "execution_date") \
                        and (_RECITAL_RE.search(context) or KANNADA_RECITAL_RE.search(context)):
                    # A recital commonly wraps across a line break, so the preceding
                    # line is part of the context.
                    add(FieldHit("parent_" + key, raw, nz.normalize_identifier(raw)
                                 if key == "registration_number" else (nz.iso_date(raw) or raw),
                                 page_no=page_no, evidence=_evidence(line), confidence=0.75))
                    continue
                elif _in_boundary_context(line, m.start(1)):
                    # Identifiers quoted inside a boundary description describe a
                    # *neighbouring* property - never the subject property.
                    if key in ("survey_number", "subdivision_number", "plot_number", "khata_number"):
                        add(FieldHit("adjoining_reference", raw, nz.normalize_survey_number(raw),
                                     page_no=page_no, evidence=_evidence(line), confidence=0.6))
                        continue
                add(_build_hit(key, raw, page_no, _evidence(line), conf, sensitive))
        for key, pattern, conf in PARTY_PATTERNS:
            for m in re.finditer(pattern, line):
                raw = nz.clean_text(m.group(1))
                if len(nz.normalize_name(raw)) < 3:
                    continue
                add(_build_hit(key, raw, page_no, _evidence(line), conf, sensitive))

        for pattern in ALL_PARENT_DEED_PATTERNS:
            for m in re.finditer(pattern, line, re.IGNORECASE):
                raw = nz.clean_text(m.group(0))
                add(FieldHit("parent_deed_reference", raw[:200], nz.clean_text(raw)[:200],
                             page_no=page_no, evidence=_evidence(line), confidence=0.7))

        for pattern, tag in ALL_MORTGAGE_SIGNALS:
            m = re.search(pattern, lower)
            if m:
                if _is_negated(context, offset + m.start()):
                    add(FieldHit("covenant_denial", "no_encumbrance_covenant", "no_encumbrance_covenant",
                                 page_no=page_no, evidence=_evidence(line), confidence=0.6))
                else:
                    add(FieldHit("mortgage_status", tag, tag, page_no=page_no,
                                 evidence=_evidence(line), confidence=0.7))
        for pattern in ALL_MORTGAGE_RELEASE_SIGNALS:
            if re.search(pattern, lower):
                add(FieldHit("mortgage_status", "release_indicated", "release_indicated",
                             page_no=page_no, evidence=_evidence(line), confidence=0.75))
        for pattern, tag in ALL_LITIGATION_SIGNALS:
            m = re.search(pattern, lower)
            if m:
                if _is_negated(context, offset + m.start()):
                    add(FieldHit("covenant_denial", "no_litigation_covenant", "no_litigation_covenant",
                                 page_no=page_no, evidence=_evidence(line), confidence=0.6))
                else:
                    add(FieldHit("litigation_mention", tag, tag, page_no=page_no,
                                 evidence=_evidence(line), confidence=0.65))
        for pattern, tag in ALL_RESTRICTION_SIGNALS:
            m = re.search(pattern, lower)
            if m:
                if _is_negated(context, offset + m.start()):
                    add(FieldHit("covenant_denial", "no_restriction_covenant", "no_restriction_covenant",
                                 page_no=page_no, evidence=_evidence(line), confidence=0.6))
                else:
                    add(FieldHit("restriction_mention", tag, tag, page_no=page_no,
                                 evidence=_evidence(line), confidence=0.65))
        for pattern in ALL_SIGNATURE_PATTERNS:
            if re.search(pattern, lower):
                add(FieldHit("signature_present", "indicated", "indicated", page_no=page_no,
                             evidence=_evidence(line), confidence=0.6))

    # Document-level passes that need more than one line of context.
    hits.extend(_extract_parties_from_prose(pages, seen, sensitive))
    hits.extend(_extract_dates_from_prose(pages, seen))
    hits.extend(_extract_areas_from_prose(pages, seen))
    hits.extend(_extract_ec(pages, seen))
    if sensitive:
        hits.extend(_extract_identity(pages, seen))
    return hits


def _build_hit(key: str, raw: str, page_no: int, evidence: str, conf: float,
               sensitive: bool) -> Optional[FieldHit]:
    raw = raw.strip(" .,:;-")
    norm: Optional[str] = raw
    number: Optional[float] = None
    unit: Optional[str] = None

    if key in NAME_KEYS:
        norm = nz.normalize_name(raw)
        if sensitive:
            raw = nz.mask_sensitive(raw)
    elif key in DATE_KEYS:
        iso = nz.iso_date(raw)
        if not iso:
            conf *= 0.5
        norm = iso or raw
    elif key in MONEY_KEYS:
        number = nz.parse_money(raw)
        norm = nz.format_money(number) if number is not None else raw
        if number is None:
            conf *= 0.5
    elif key in AREA_KEYS:
        parsed = nz.parse_area(raw)
        if not parsed:
            # Not an extent at all: the label pattern ran on into the sentence
            # after it. Reported at low confidence this filled the extent row
            # with prose and made the document look as though it disagreed with
            # the others about the area.
            return None
        value, unit, sqm = parsed
        number, norm = value, "{} {}".format(nz.format_area(value, unit), "({:g} sq m)".format(sqm))
    elif key == "survey_number":
        norm = nz.normalize_survey_number(raw)
    elif key in IDENTIFIER_KEYS:
        norm = nz.normalize_identifier(raw)
    elif key in _PLACE_KEYS:
        # "of Arakere village" leaves the preposition attached, and the report then
        # shows "OF ARAKERE" conflicting with "Arakere" - the same place twice.
        norm = nz.normalize_place(raw)
    else:
        norm = nz.clean_text(raw)
        if sensitive:
            norm = nz.mask_sensitive(norm)

    return FieldHit(key=key, value_raw=raw[:400], value_norm=(norm or "")[:400], value_number=number,
                    unit=unit, page_no=page_no, evidence=evidence, confidence=round(min(conf, 0.98), 3))


_ROLE_TO_KEY = {
    "VENDOR": "party_seller", "SELLER": "party_seller", "TRANSFEROR": "party_seller",
    "FIRST PARTY": "party_seller", "DONOR": "party_seller", "SETTLOR": "party_seller",
    "RELEASOR": "party_seller", "MORTGAGOR": "party_mortgagor", "LESSOR": "party_seller",
    "PURCHASER": "party_buyer", "BUYER": "party_buyer", "TRANSFEREE": "party_buyer",
    "SECOND PARTY": "party_buyer", "DONEE": "party_buyer", "SETTLEE": "party_buyer",
    "RELEASEE": "party_buyer", "MORTGAGEE": "party_mortgagee", "LESSEE": "party_buyer",
}
_ROLE_MARKER_RE = re.compile(
    r"hereinafter\s+(?:called|referred\s+to\s+as)\s+(?:the\s+)?[\"\u201c']?"
    r"(VENDOR|SELLER|TRANSFEROR|FIRST\s+PARTY|DONOR|SETTLOR|RELEASOR|MORTGAGOR|LESSOR|"
    r"PURCHASER|BUYER|TRANSFEREE|SECOND\s+PARTY|DONEE|SETTLEE|RELEASEE|MORTGAGEE|LESSEE)",
    re.IGNORECASE,
)
_HONORIFIC_NAME_RE = re.compile(
    r"\b(?:Shri|Sri|Smti|Smt|Kumari|Kum|Messrs|M/s|Mrs|Mr|Ms|Dr)\.?\s+"
    r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})"
)
_PLAIN_NAME_RE = re.compile(
    r"(?:^|\n)\s*(?:BETWEEN|AND|WITH)\s+([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})",
    re.MULTILINE,
)
_ORG_NAME_RE = re.compile(
    r"\b([A-Z][A-Za-z&'\-]+(?:\s+[A-Z][A-Za-z&'\-]+){0,4}\s+"
    r"(?:Bank|Limited|Ltd|Corporation|Society|Trust|Association|Developers|Builders|Housing))\b"
)


#: Parties are separated by BETWEEN / AND, or numbered in a list ("1. ...", "2. ...").
_PARTY_DELIMITER_RE = re.compile(
    r"(?:^|\n)\s*(?:BETWEEN|AND|WITH)\b|(?:^|\n)\s*\d+[.)]\s", re.MULTILINE)
#: "Smt Latha Rao W/o Sri Mohan Rao" - the name after W/o is a relation, not a party.
_RELATION_PREFIX_RE = re.compile(r"(?:s/o|w/o|d/o|c/o|son of|daughter of|wife of)\s*$", re.IGNORECASE)


def _first_party_name(window: str) -> Optional[str]:
    for m in _HONORIFIC_NAME_RE.finditer(window):
        preceding = window[max(0, m.start() - 12):m.start()]
        if _RELATION_PREFIX_RE.search(preceding.strip() + " ") or _RELATION_PREFIX_RE.search(preceding):
            continue
        return m.group(1)
    org = _ORG_NAME_RE.search(window)
    if org:
        return org.group(1)
    plain = _PLAIN_NAME_RE.search(window)
    if plain:
        return plain.group(1)
    bare = re.match(r"\s*([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})", window)
    return bare.group(1) if bare else None


def _extract_parties_from_prose(pages, seen, sensitive: bool) -> List[FieldHit]:
    """Deeds name their parties in prose, often several lines before the role word."""
    out: List[FieldHit] = []
    for page in pages:
        blob = page.text or ""
        for marker in _ROLE_MARKER_RE.finditer(blob):
            role = re.sub(r"\s+", " ", marker.group(1)).upper()
            key = _ROLE_TO_KEY.get(role)
            if not key:
                continue
            window = blob[max(0, marker.start() - 500):marker.start()]
            # Keep only the text after the last party delimiter so that the name
            # of the *previous* party is not picked up.
            delimiters = list(_PARTY_DELIMITER_RE.finditer(window))
            if delimiters:
                window = window[delimiters[-1].end():]
            name = _first_party_name(window) or _first_party_name(
                blob[max(0, marker.start() - 500):marker.start()])
            if not name:
                continue
            normalised = nz.normalize_name(name)
            if len(normalised) < 3:
                continue
            if sensitive:
                normalised = nz.mask_sensitive(normalised)
            sig = (key, normalised.lower())
            if sig in seen:
                continue
            seen.add(sig)
            out.append(FieldHit(
                key=key, value_raw=name, value_norm=normalised, page_no=page.page_no,
                evidence=_evidence(blob[max(0, marker.start() - 160):marker.end() + 30]),
                confidence=0.85,
            ))
    return out


def _extract_dates_from_prose(pages, seen) -> List[FieldHit]:
    """Pick up `made on this 12th day of March 2015` style execution dates."""
    out: List[FieldHit] = []
    pattern = re.compile(
        r"(?:made|executed|entered\s+into|dated)\s+(?:and\s+executed\s+)?(?:on\s+)?(?:this\s+)?"
        r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?[A-Za-z]{3,9}[,\s]+\d{4}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        re.IGNORECASE,
    )
    for page_no, blob in _page_blobs(pages):
        for m in pattern.finditer(blob):
            iso = nz.iso_date(m.group(1))
            if not iso or ("execution_date", iso) in seen:
                continue
            seen.add(("execution_date", iso))
            out.append(FieldHit("execution_date", m.group(1), iso, page_no=page_no,
                                evidence=_evidence(m.group(0)), confidence=0.8))
    return out


#: An area immediately preceded by one of these labels is not the property extent.
_OTHER_AREA_LABEL_RE = re.compile(
    "(?:kharab|kharb|ಖರಾಬು|ಖರಾಬ|built[\\s\\-]*up|plinth|carpet|"
    "super[\\s\\-]*built|ನಿರ್ಮಿತ|ಉದ್ದಿಷ್ಟ)"
    "[^\\n]{0,24}$",
    re.IGNORECASE,
)


def _extract_areas_from_prose(pages, seen) -> List[FieldHit]:
    out: List[FieldHit] = []
    pattern = re.compile(
        # Kannada units are listed alongside the English ones: the normaliser
        # already understands ಎಕರೆ and ಗುಂಟೆ, but an extent written in Kannada was
        # never found in the first place, so a Kannada deed reported no area at all.
        r"((?:\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)\s*(?:acres?|gunthas?|guntas?|cents?|hectares?|ಎಕರೆ|ಎಕರ|ಎಕ್ರೆ|ಗುಂಟೆಗಳು|ಗುಂಟೆ|ಗುಂಠೆ|sq\.?\s*(?:feet|ft|metres?|meters?|m|yards?|yds?)|ಚದರ\s*ಅಡಿ|ಚದರಡಿ|ಚದರ\s*ಮೀಟರ್|ankanams?|grounds?)"
        r"(?:\s*(?:and\s+)?\d{1,3}(?:\.\d+)?\s*(?:gunthas?|guntas?|ಗುಂಟೆಗಳು|ಗುಂಟೆ|ಗುಂಠೆ))?)",
        re.IGNORECASE,
    )
    for page_no, blob in _page_blobs(pages):
        for m in pattern.finditer(blob):
            parsed = nz.parse_area(m.group(1))
            if not parsed:
                continue
            if _OTHER_AREA_LABEL_RE.search(blob[max(0, m.start() - 40):m.start()]):
                # Kharab is unusable waste within the survey number and built-up
                # area is a subset of the plot; neither is the extent being sold,
                # and each has its own field.
                continue
            value, unit, sqm = parsed
            norm = "{} ({:g} sq m)".format(nz.format_area(value, unit), sqm)
            if ("property_area", norm.lower()) in seen:
                continue
            seen.add(("property_area", norm.lower()))
            start = max(0, m.start() - 90)
            out.append(FieldHit("property_area", m.group(1), norm, value_number=value, unit=unit,
                                page_no=page_no, evidence=_evidence(blob[start:m.end() + 40]),
                                confidence=0.7))
    return out


def _extract_ec(pages, seen) -> List[FieldHit]:
    """Encumbrance certificates: certified period, entry count and nil declarations."""
    out: List[FieldHit] = []
    full = "\n".join((p.text or "") for p in pages)
    lower = full.lower()

    kn_period = KANNADA_EC_PERIOD_RE.search(full)
    if kn_period:
        page_no = _page_for_offset(pages, kn_period.start())
        f_iso, t_iso = nz.iso_date(kn_period.group(1)), nz.iso_date(kn_period.group(2))
        if f_iso and ("ec_period_from", f_iso) not in seen:
            seen.add(("ec_period_from", f_iso))
            out.append(FieldHit("ec_period_from", kn_period.group(1), f_iso, page_no=page_no,
                                evidence=_evidence(kn_period.group(0)), confidence=0.9))
        if t_iso and ("ec_period_to", t_iso) not in seen:
            seen.add(("ec_period_to", t_iso))
            out.append(FieldHit("ec_period_to", kn_period.group(2), t_iso, page_no=page_no,
                                evidence=_evidence(kn_period.group(0)), confidence=0.9))

    period = re.search(
        r"(?:period|from)\s*[:\-]?\s*(\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})"
        r"\s*(?:to|till|until|up\s*to|-|–)\s*(\d{1,2}[\-/.]\d{1,2}[\-/.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})",
        full, re.IGNORECASE,
    )
    if period:
        page_no = _page_for_offset(pages, period.start())
        f_iso, t_iso = nz.iso_date(period.group(1)), nz.iso_date(period.group(2))
        if f_iso and ("ec_period_from", f_iso) not in seen:
            seen.add(("ec_period_from", f_iso))
            out.append(FieldHit("ec_period_from", period.group(1), f_iso, page_no=page_no,
                                evidence=_evidence(period.group(0)), confidence=0.9))
        if t_iso and ("ec_period_to", t_iso) not in seen:
            seen.add(("ec_period_to", t_iso))
            out.append(FieldHit("ec_period_to", period.group(2), t_iso, page_no=page_no,
                                evidence=_evidence(period.group(0)), confidence=0.9))

    if any(re.search(p, lower, re.MULTILINE) for p in EC_NIL_PATTERNS) or \
            any(re.search(p, full) for p in KANNADA_EC_NIL_PATTERNS):
        out.append(FieldHit("ec_nil", "true", "true", page_no=1,
                            evidence="The certificate states that no encumbrance entries were found.",
                            confidence=0.8))

    entries = len(re.findall(r"^\s*\d{1,3}[.)]\s+", full, re.MULTILINE))
    if entries:
        out.append(FieldHit("ec_entries", str(entries), str(entries), value_number=float(entries),
                            page_no=1, evidence="{} numbered entries detected in the certificate.".format(entries),
                            confidence=0.5))
    return out


def _extract_identity(pages, seen) -> List[FieldHit]:
    out: List[FieldHit] = []
    full = "\n".join((p.text or "") for p in pages)
    for m in re.finditer(r"\b(\d{4}\s?\d{4}\s?\d{4})\b|\b([A-Z]{5}\d{4}[A-Z])\b", full):
        raw = m.group(0)
        masked = nz.mask_sensitive(raw)
        if ("identity_number", masked.lower()) in seen:
            continue
        seen.add(("identity_number", masked.lower()))
        out.append(FieldHit("identity_number", masked, masked,
                            page_no=_page_for_offset(pages, m.start()),
                            evidence="An identity number is present in this document (value masked).",
                            confidence=0.8, provenance="explicit"))
    return out


def _page_for_offset(pages, offset: int) -> int:
    cursor = 0
    for page in pages:
        length = len(page.text or "") + 1
        if offset < cursor + length:
            return page.page_no
        cursor += length
    return pages[-1].page_no if pages else 1


def detect_integrity_issues(pages, extraction_issues: Sequence[str]) -> List[Dict[str, Any]]:
    """Observable document-integrity concerns.  These are *observations*, never verdicts."""
    pages = [_DigitNormalisedPage(page) for page in pages]
    issues: List[Dict[str, Any]] = []
    full = "\n".join((p.text or "") for p in pages)

    seen_pages = set()
    declared_total = None
    for m in re.finditer(r"page\s+(\d{1,3})\s+of\s+(\d{1,3})", full, re.IGNORECASE):
        seen_pages.add(int(m.group(1)))
        declared_total = max(declared_total or 0, int(m.group(2)))
    if declared_total and len(pages) < declared_total:
        issues.append({
            "type": "missing_pages",
            "detail": "The document declares {} pages but only {} were supplied.".format(declared_total, len(pages)),
            "severity": "high",
        })
    if declared_total and seen_pages and len(pages) < declared_total:
        missing = sorted(set(range(1, declared_total + 1)) - seen_pages)
        # Only meaningful when the file genuinely holds fewer pages than it declares;
        # a page marker printed on the first page only is normal.
        if missing:
            issues.append({
                "type": "missing_pages",
                "detail": "Page markers suggest pages {} are not present.".format(
                    ", ".join(str(x) for x in missing[:10])),
                "severity": "high",
            })

    if re.search(r"\b(?:annexure|schedule|exhibit|appendix)\s+([A-Z0-9]{1,3})\b", full, re.IGNORECASE):
        referenced = {m.group(1).upper() for m in re.finditer(
            r"\b(?:annexure|schedule|exhibit|appendix)\s+([A-Z0-9]{1,3})\b", full, re.IGNORECASE)}
        present = {m.group(1).upper() for m in re.finditer(
            r"^\s*(?:annexure|schedule|exhibit|appendix)\s+([A-Z0-9]{1,3})\b", full, re.IGNORECASE | re.MULTILINE)}
        absent = sorted(referenced - present)
        if absent:
            issues.append({
                "type": "missing_annexure",
                "detail": "Annexure/schedule {} is referenced but no corresponding heading was found.".format(
                    ", ".join(absent[:6])),
                "severity": "medium",
            })

    empty = [p.page_no for p in pages if len((p.text or "").strip()) < 40]
    if empty:
        issues.append({
            "type": "unreadable_pages",
            "detail": "Page(s) {} yielded little or no text and could not be assessed.".format(
                ", ".join(str(p) for p in empty[:10])),
            "severity": "medium",
        })

    low_conf = [p.page_no for p in pages if p.ocr_used and p.confidence < 0.6]
    if low_conf:
        issues.append({
            "type": "ocr_uncertainty",
            "detail": "OCR confidence is low on page(s) {}; extracted values need checking against the original.".format(
                ", ".join(str(p) for p in low_conf[:10])),
            "severity": "medium",
        })

    for issue in extraction_issues:
        issues.append({"type": "extraction_note", "detail": issue, "severity": "low"})
    return issues
