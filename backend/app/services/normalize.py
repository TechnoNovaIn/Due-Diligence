"""Deterministic normalisation helpers.

Dates, areas, money amounts and identifiers are *never* left to the language
model: they are parsed by these rules so that comparisons across documents are
reproducible and explainable.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Optional, Tuple

from dateutil import parser as dateparser
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------
#: Kannada digits, which appear throughout Bhoomi and Kaveri records.
KANNADA_DIGITS = "೦೧೨೩೪೫೬೭೮೯"
_KANNADA_DIGIT_MAP = {ord(d): str(i) for i, d in enumerate(KANNADA_DIGITS)}
#: Devanagari digits, for documents that mix scripts.
_DEVANAGARI_DIGIT_MAP = {ord(d): str(i) for i, d in enumerate("०१२३४५६७८९")}
_DIGIT_MAP = dict(_KANNADA_DIGIT_MAP)
_DIGIT_MAP.update(_DEVANAGARI_DIGIT_MAP)

_KANNADA_RANGE = re.compile(r"[\u0C80-\u0CFF]")


def has_kannada(text: Optional[str]) -> bool:
    return bool(_KANNADA_RANGE.search(text or ""))


def script_of(text: Optional[str]) -> str:
    """``kn``, ``en`` or ``mixed`` - used to pick the right patterns and report honestly."""
    body = text or ""
    if not body.strip():
        return "unknown"
    kannada = len(_KANNADA_RANGE.findall(body))
    latin = len(re.findall(r"[A-Za-z]", body))
    if kannada and latin:
        ratio = kannada / float(kannada + latin)
        if ratio > 0.75:
            return "kn"
        if ratio < 0.15:
            return "en"
        return "mixed"
    if kannada:
        return "kn"
    return "en"


def westernize_digits(text: Optional[str]) -> str:
    """``೧೨೩/೪ಬಿ`` -> ``123/4ಬಿ``. Applied before any numeric parsing."""
    if not text:
        return ""
    return text.translate(_DIGIT_MAP)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
_WS_RE = re.compile(r"[ \t ]+")
_HONORIFICS = (
    "sri", "shri", "smt", "smti", "mr", "mrs", "ms", "miss", "dr", "late",
    "m/s", "messrs", "sri.", "kum", "kumari",
    # Kannada honorifics
    "ಶ್ರೀ", "ಶ್ರೀಮತಿ", "ಶ್ರೀಯುತ", "ಕುಮಾರಿ", "ದಿವಂಗತ", "ಮೃತ",
)
#: Connectives that regularly get swept into a captured party name.
_LEADING_NOISE = ("between", "and", "by", "the", "of", "with", "whereas", "among", "shri",
                  "ಮತ್ತು", "ಹಾಗೂ", "ಇವರ", "ಇವರು", "ಶ್ರೀ")
_RELATION_RE = re.compile(
    r"(?:\b(?:s/o|d/o|w/o|c/o|son of|daughter of|wife of|aged about|aged)\b"
    # Kannada: bin (s/o), kom (w/o), tande (father), vayassu (aged), vaasi (resident of).
    # A trailing \b cannot be used here: Kannada vowel signs and the anusvara are
    # combining marks, which are not word characters, so no boundary exists after them.
    r"|(?:ಬಿನ್|ಕೋಂ|ತಂದೆ|ಮಗ|ಮಗಳು|ಪತ್ನಿ|ಗಂಡ|ವಯಸ್ಸು|ವಾಸಿ|ರವರ ಮಗ|ರವರ ಮಗಳು)(?=\s|,|$)).*$",
    re.IGNORECASE,
)


def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFC", value)
    value = westernize_digits(value)
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    value = _WS_RE.sub(" ", value)
    return value.strip()


def normalize_place(value: Optional[str]) -> str:
    """Clean a place name: drop a leading preposition and trailing punctuation.

    Unlike a person's name a place keeps its own words, so this does not strip
    honorifics - only the joining words a label pattern drags in with it.
    """
    text = clean_text(value)
    if not text:
        return ""
    text = re.sub(r"[,\.]+$", "", text)
    tokens = [tok for tok in re.split(r"\s+", text) if tok]
    while tokens and tokens[0].strip(".,:;()").lower() in _LEADING_NOISE:
        tokens.pop(0)
    return " ".join(tokens).strip()


def normalize_name(value: Optional[str]) -> str:
    """Strip honorifics, relationship clauses and punctuation noise from a name."""
    text = clean_text(value)
    if not text:
        return ""
    text = _RELATION_RE.sub("", text)
    text = re.sub(r"[,\.]+$", "", text)
    tokens = [t for t in re.split(r"\s+", text) if t]
    while tokens and tokens[0].strip(".,:;()").lower() in _LEADING_NOISE:
        tokens.pop(0)
    out = []
    for tok in tokens:
        bare = tok.strip(".,:;()").lower()
        if bare in _HONORIFICS:
            continue
        out.append(tok.strip(".,:;()"))
    cleaned = " ".join(out).strip()
    return re.sub(r"\s+", " ", cleaned).title()


def names_match(a: Optional[str], b: Optional[str], threshold: int = 88) -> bool:
    """Fuzzy name equivalence tolerant of initials, ordering and spelling drift."""
    na, nb = normalize_name(a).lower(), normalize_name(b).lower()
    if not na or not nb:
        return False
    if na == nb:
        return True
    if fuzz.token_sort_ratio(na, nb) >= threshold:
        return True
    # "K. Ramesh" vs "Ramesh Kumar" style initials
    ta, tb = set(na.replace(".", " ").split()), set(nb.replace(".", " ").split())
    long_a = {t for t in ta if len(t) > 1}
    long_b = {t for t in tb if len(t) > 1}
    if long_a and long_b and (long_a <= long_b or long_b <= long_a):
        return True
    return False


def name_similarity(a: Optional[str], b: Optional[str]) -> int:
    na, nb = normalize_name(a).lower(), normalize_name(b).lower()
    if not na or not nb:
        return 0
    return int(fuzz.token_sort_ratio(na, nb))


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),                       # ISO
    re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b"),          # dd/mm/yyyy
]
#: Kannada month names, mapped to the month number.
KANNADA_MONTHS = {
    "ಜನವರಿ": 1, "ಫೆಬ್ರವರಿ": 2, "ಫೆಬ್ರುವರಿ": 2, "ಮಾರ್ಚ್": 3, "ಮಾರ್ಚಿ": 3,
    "ಏಪ್ರಿಲ್": 4, "ಎಪ್ರಿಲ್": 4, "ಮೇ": 5, "ಜೂನ್": 6, "ಜುಲೈ": 7, "ಜುಲಾಯಿ": 7,
    "ಆಗಸ್ಟ್": 8, "ಆಗಷ್ಟ್": 8, "ಸೆಪ್ಟೆಂಬರ್": 9, "ಸೆಪ್ಟಂಬರ್": 9,
    "ಅಕ್ಟೋಬರ್": 10, "ಅಕ್ಟೊಬರ್": 10, "ನವೆಂಬರ್": 11, "ನವಂಬರ್": 11,
    "ಡಿಸೆಂಬರ್": 12, "ಡಿಸಂಬರ್": 12,
}
_KN_DATE_RE = re.compile(
    r"(\d{1,2})\s*(?:ನೇ|ನೆ)?\s*(" + "|".join(sorted(KANNADA_MONTHS, key=len, reverse=True)) +
    r")\s*,?\s*(\d{4})"
)

_TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?"
    r"(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)[,\s]+(\d{4})\b",
    re.IGNORECASE,
)
_TEXT_DATE_RE2 = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})\b",
    re.IGNORECASE,
)


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse an Indian-convention (day-first) date.  Returns ``None`` when unsure."""
    text = clean_text(value)
    if not text:
        return None
    m = _DATE_PATTERNS[0].search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _KN_DATE_RE.search(text)
    if m:
        try:
            return date(int(m.group(3)), KANNADA_MONTHS[m.group(2)], int(m.group(1)))
        except (ValueError, KeyError):
            return None
    m = _TEXT_DATE_RE.search(text) or _TEXT_DATE_RE2.search(text)
    if m:
        try:
            return dateparser.parse(m.group(0), dayfirst=True, fuzzy=True).date()
        except (ValueError, OverflowError, TypeError):
            return None
    m = _DATE_PATTERNS[1].search(text)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 50 else 1900
        if d > 12 and mth > 12:
            return None
        if mth > 12:  # clearly mm/dd written the other way round
            d, mth = mth, d
        try:
            return date(y, mth, d)
        except ValueError:
            return None
    return None


def iso_date(value: Optional[str]) -> Optional[str]:
    d = parse_date(value)
    return d.isoformat() if d else None


def format_date(value: Optional[str]) -> str:
    d = parse_date(value)
    return d.strftime("%d %b %Y") if d else (clean_text(value) or "—")


# ---------------------------------------------------------------------------
# Area
# ---------------------------------------------------------------------------
#: Conversion factors into square metres (the canonical internal unit).
AREA_UNITS_SQM = {
    "sqm": 1.0,
    "sqft": 0.09290304,
    "sqyd": 0.83612736,
    "acre": 4046.8564224,
    "guntha": 101.17141056,     # 1/40 acre
    "cent": 40.468564224,       # 1/100 acre
    "hectare": 10000.0,
    "ankanam": 6.68901888,      # 72 sq ft
    "ground": 222.967296,       # 2400 sq ft
    "kanal": 505.857,
    "marla": 25.2929,
    "bigha_ka": 2529.285,       # regional; flagged as approximate
}

_UNIT_ALIASES = {
    "sq.ft": "sqft", "sq ft": "sqft", "sqft": "sqft", "sq. ft": "sqft", "square feet": "sqft",
    "square foot": "sqft", "sft": "sqft", "ft2": "sqft", "sq.feet": "sqft", "sq feet": "sqft",
    "sq.m": "sqm", "sq m": "sqm", "sqm": "sqm", "square metre": "sqm", "square meter": "sqm",
    "square metres": "sqm", "square meters": "sqm", "m2": "sqm",
    "sq.yd": "sqyd", "sq yd": "sqyd", "sqyd": "sqyd", "square yard": "sqyd", "square yards": "sqyd",
    "acre": "acre", "acres": "acre", "ac": "acre",
    "guntha": "guntha", "gunthas": "guntha", "gunta": "guntha", "guntas": "guntha",
    "cent": "cent", "cents": "cent",
    "hectare": "hectare", "hectares": "hectare", "ha": "hectare",
    "ankanam": "ankanam", "ankanams": "ankanam", "ankana": "ankanam",
    "ground": "ground", "grounds": "ground",
    "kanal": "kanal", "marla": "marla", "bigha": "bigha_ka",
    # Kannada unit names as they appear in RTC, deeds and khata extracts.
    "ಎಕರೆ": "acre", "ಎಕರ": "acre", "ಎಕ್ರೆ": "acre",
    "ಗುಂಟೆ": "guntha", "ಗುಂಟೆಗಳು": "guntha", "ಗುಂಠೆ": "guntha",
    "ಸೆಂಟ್": "cent", "ಸೆಂಟ್ಸ್": "cent", "ಸೆಂಟು": "cent",
    "ಹೆಕ್ಟೇರ್": "hectare", "ಹೆಕ್ಟೇರು": "hectare", "ಹೆಕ್ಟೇರ": "hectare",
    "ಚದರ ಅಡಿ": "sqft", "ಚ.ಅಡಿ": "sqft", "ಚದರಡಿ": "sqft", "ಅಡಿ": "sqft",
    "ಚದರ ಮೀಟರ್": "sqm", "ಚ.ಮೀ": "sqm", "ಚದರ ಮೀ": "sqm",
    "ಚದರ ಗಜ": "sqyd", "ಗಜ": "sqyd",
    "ಅಂಕಣ": "ankanam", "ಅಂಕಣಂ": "ankanam",
}

UNIT_LABELS = {
    "sqm": "sq m", "sqft": "sq ft", "sqyd": "sq yd", "acre": "acre", "guntha": "guntha",
    "cent": "cent", "hectare": "hectare", "ankanam": "ankanam", "ground": "ground",
    "kanal": "kanal", "marla": "marla", "bigha_ka": "bigha",
}

_UNIT_RE = "|".join(sorted((re.escape(k) for k in _UNIT_ALIASES), key=len, reverse=True))
#: A trailing \b is unusable here: Kannada unit names end in a vowel sign, which is a
#: combining mark and therefore not a word character, so no boundary exists after them.
_UNIT_END = r"(?=[\s,.;:)\]/]|$)"
_AREA_RE = re.compile(
    r"(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)\s*(" + _UNIT_RE + r")" + _UNIT_END,
    re.IGNORECASE,
)
# "2 acres 15 guntas" and the Kannada "೨ ಎಕರೆ ೧೫ ಗುಂಟೆ"
_COMPOUND_AREA_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:acres?|ac\b|ಎಕರೆ|ಎಕರ|ಎಕ್ರೆ)"
    r"[\s,]*(?:and|ಮತ್ತು)?[\s,]*"
    r"(\d+(?:\.\d+)?)\s*(?:gunthas?|guntas?|ಗುಂಟೆಗಳು|ಗುಂಟೆ|ಗುಂಠೆ)",
    re.IGNORECASE,
)


def canonical_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    key = clean_text(unit).lower().rstrip(".")
    return _UNIT_ALIASES.get(key) or _UNIT_ALIASES.get(key.replace(" ", ""))


def parse_area(text: Optional[str]) -> Optional[Tuple[float, str, float]]:
    """Return ``(value, canonical_unit, square_metres)`` for the first area found."""
    s = clean_text(text)
    if not s:
        return None
    m = _COMPOUND_AREA_RE.search(s)
    if m:
        acres = float(m.group(1))
        gunthas = float(m.group(2))
        sqm = acres * AREA_UNITS_SQM["acre"] + gunthas * AREA_UNITS_SQM["guntha"]
        return (round(acres + gunthas / 40.0, 4), "acre", round(sqm, 3))
    m = _AREA_RE.search(s)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    unit = canonical_unit(m.group(2))
    if not unit:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return (value, unit, round(value * AREA_UNITS_SQM[unit], 3))


def area_to_sqm(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    cu = canonical_unit(unit)
    if value is None or cu is None:
        return None
    return round(value * AREA_UNITS_SQM[cu], 3)


def format_area(value: Optional[float], unit: Optional[str]) -> str:
    if value is None:
        return "—"
    cu = canonical_unit(unit) or "sqm"
    return "{:g} {}".format(round(value, 4), UNIT_LABELS.get(cu, cu))


def area_difference_pct(sqm_a: Optional[float], sqm_b: Optional[float]) -> Optional[float]:
    if not sqm_a or not sqm_b:
        return None
    base = max(sqm_a, sqm_b)
    if base == 0:
        return None
    return round(abs(sqm_a - sqm_b) / base * 100.0, 2)


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------
_MONEY_RE = re.compile(
    r"(?:rs\.?|inr|₹|rupees|ರೂ\.?|ರೂಪಾಯಿ(?:ಗಳು)?)\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_WORD_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹|rupees|ರೂ\.?|ರೂಪಾಯಿ)?\s*([\d,]+(?:\.\d+)?)\s*"
    r"(crores?|lakhs?|lacs?|thousands?|ಕೋಟಿ|ಲಕ್ಷ|ಸಾವಿರ)(?=\s|$|\W)",
    re.IGNORECASE,
)
_WORD_MULT = {"crore": 1e7, "crores": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5,
              "lacs": 1e5, "thousand": 1e3, "thousands": 1e3,
              "ಕೋಟಿ": 1e7, "ಲಕ್ಷ": 1e5, "ಸಾವಿರ": 1e3}


def parse_money(text: Optional[str]) -> Optional[float]:
    s = clean_text(text)
    if not s:
        return None
    m = _WORD_AMOUNT_RE.search(s)
    if m:
        try:
            return float(m.group(1).replace(",", "")) * _WORD_MULT[m.group(2).lower()]
        except (ValueError, KeyError):
            pass
    m = _MONEY_RE.search(s)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def format_money(value: Optional[float]) -> str:
    """Indian digit grouping: 45,00,000."""
    if value is None:
        return "—"
    neg = value < 0
    whole = int(abs(value))
    frac = abs(value) - whole
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    out = "Rs. " + s + (".{:02d}".format(int(round(frac * 100))) if frac >= 0.005 else "")
    return ("-" if neg else "") + out


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------
_SURVEY_CLEAN_RE = re.compile(
    r"(?:\b(?:sy\.?|survey|s\.?)\s*(?:no\.?|number)?"
    r"|ಸರ್ವೇ|ಸರ್ವೆ|ಸ\.ನಂ\.?|ಸಂಖ್ಯೆ|ನಂ\.?)\s*",
    re.IGNORECASE,
)


def normalize_survey_number(value: Optional[str]) -> str:
    """``Sy. No. 123/4 B`` -> ``123/4B``."""
    s = clean_text(value)
    if not s:
        return ""
    s = s.replace("\u200c", "").replace("\u200d", "")
    s = _SURVEY_CLEAN_RE.sub("", s)
    s = s.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"(?<=\d)\s+(?=[A-Za-z]\b)", "", s)
    s = s.strip(" .,;:")
    return s.upper()


def survey_numbers_match(a: Optional[str], b: Optional[str]) -> bool:
    na, nb = normalize_survey_number(a), normalize_survey_number(b)
    if not na or not nb:
        return False
    return na == nb


def survey_number_root(value: Optional[str]) -> str:
    """Root block of a survey number: ``123/4B`` -> ``123``."""
    n = normalize_survey_number(value)
    return re.split(r"[/\-]", n)[0] if n else ""


def normalize_identifier(value: Optional[str]) -> str:
    """Keep Latin, digits and Kannada: survey and document numbers mix all three."""
    s = clean_text(value).upper()
    # ZWJ/ZWNJ carry no meaning in an identifier but break equality comparisons.
    s = s.replace("\u200c", "").replace("\u200d", "")
    return re.sub(r"[^A-Z0-9/\-\u0C80-\u0CFF]", "", s)


def mask_sensitive(value: Optional[str]) -> str:
    """Mask Aadhaar/PAN-like identifiers before they reach a report or a log."""
    s = clean_text(value)
    if not s:
        return ""
    s = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "XXXX XXXX ####", s)
    s = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "XXXXX####X", s)
    return s


def today() -> date:
    return datetime.utcnow().date()
