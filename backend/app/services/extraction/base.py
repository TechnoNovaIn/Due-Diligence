from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

#: Control characters that carry no text, keeping newline and tab.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
#: Zero-width and invisible formatting characters.
#: Kaveri and Bhoomi PDFs embed these *inside* words - "ನ\x1fಮೂನೆ" for "ನಮೂನೆ" -
#: which silently breaks every phrase match unless they are removed rather than
#: turned into spaces.
_INVISIBLE_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")


def _strip_midword_returns(text: str) -> str:
    """Delete a carriage return that splits a word; keep every other one as a
    line break.

    A real encumbrance certificate splits the Kannada word for "number" in
    half with one. The giveaway is the character *before* it: a combining mark.
    A line can never begin where a vowel sign or anusvara left off, so a return
    in that position is noise from the PDF producer and the two halves belong
    together. After a letter, a digit or punctuation it is ambiguous at best,
    and is treated as the line break it looks like.
    """
    if "\r" not in text:
        return text
    out = []
    for index, ch in enumerate(text):
        if ch != "\r":
            out.append(ch)
            continue
        previous = text[index - 1] if index else ""
        following = text[index + 1] if index + 1 < len(text) else ""
        splits_a_word = (
            previous
            and following
            and unicodedata.category(previous).startswith("M")
            and unicodedata.category(following).startswith("L")
        )
        out.append("" if splits_a_word else "\n")
    return "".join(out)


def sanitise_text(text: Optional[str]) -> str:
    """Remove invisible characters that would break word matching.

    They are *deleted*, not replaced with a space: a control character sitting
    between two letters of a word is noise from the PDF producer, and replacing
    it with a space would split the word in two.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n")
    text = _strip_midword_returns(text)
    text = _CONTROL_RE.sub("", text)
    return _INVISIBLE_RE.sub("", text)



@dataclass
class PageText:
    page_no: int
    text: str
    ocr_used: bool = False
    confidence: float = 1.0

    @property
    def char_count(self) -> int:
        return len(self.text or "")


@dataclass
class ExtractionResult:
    pages: List[PageText] = field(default_factory=list)
    method: str = "none"
    ocr_used: bool = False
    issues: List[str] = field(default_factory=list)
    ok: bool = True
    error: Optional[str] = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def char_count(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def confidence(self) -> float:
        """Mean page confidence, penalised when pages came back near-empty."""
        if not self.pages:
            return 0.0
        total = 0.0
        for p in self.pages:
            conf = p.confidence
            if p.char_count < 40:
                conf *= 0.3
            elif p.char_count < 200:
                conf *= 0.7
            total += conf
        return round(total / len(self.pages), 3)

    @property
    def empty_pages(self) -> List[int]:
        return [p.page_no for p in self.pages if p.char_count < 40]
