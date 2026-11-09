# -*- coding: utf-8 -*-
"""Kannada PDF rendering.

ReportLab draws glyphs in the order it is given them and performs no
complex-script shaping, so Kannada conjuncts come out broken - ``ಪ್ರಮಾಣ``
renders as ``ಪ್‌ರಮಾಣ``. That is not acceptable in a document people read, file
and act on.

MuPDF shapes correctly, and its ``Story`` API paginates a flowing HTML document
across as many pages as it needs. The Kannada PDF is therefore laid out from the
report's own HTML. The English PDF keeps the ReportLab typesetting.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import fitz

from .report_i18n import kannada_font, latin_font

log = logging.getLogger(__name__)

#: Shaped Kannada conjuncts are drawn as composite glyphs that carry no reverse
#: mapping to Unicode, so text copied or searched out of this PDF is unreliable
#: even though the page itself reads correctly. The HTML report is the
#: machine-readable form; this is surfaced in the interface and the docs.
TEXT_LAYER_CAVEAT = {
    "en": ("The Kannada PDF reads and prints correctly, but copying text out of it or "
           "searching it inside a PDF reader is unreliable, because shaped conjuncts carry "
           "no reverse mapping to Unicode. Use the HTML report when the text itself is needed."),
    "kn": ("ಕನ್ನಡ ಪಿಡಿಎಫ್ ಸರಿಯಾಗಿ ಕಾಣಿಸುತ್ತದೆ ಮತ್ತು ಮುದ್ರಿಸುತ್ತದೆ, ಆದರೆ ಅದರಿಂದ ಪಠ್ಯವನ್ನು ನಕಲಿಸುವುದು "
           "ಅಥವಾ ಪಿಡಿಎಫ್ ಓದುಗದಲ್ಲಿ ಹುಡುಕುವುದು ವಿಶ್ವಾಸಾರ್ಹವಲ್ಲ. ಪಠ್ಯವೇ ಬೇಕಿದ್ದರೆ ಎಚ್‌ಟಿಎಂಎಲ್ ವರದಿ ಬಳಸಿ."),
}

PAGE_WIDTH, PAGE_HEIGHT = 595.0, 842.0
MARGIN = 36.0
FOOTER_HEIGHT = 22.0

#: Print styling. The HTML report's own stylesheet targets a screen; this is
#: narrower and quieter, and names the embedded fonts.
PRINT_CSS = """
@font-face { font-family: knmain; src: url('kannada.ttf'); }
@font-face { font-family: latin; src: url('latin.ttf'); }
* { font-family: knmain, latin, sans-serif; }
body { font-size: 8.5pt; line-height: 1.5; color: #15181d; }
h1 { font-size: 15pt; margin: 0 0 3pt; }
h2 { font-size: 11pt; margin: 11pt 0 4pt; border-bottom: 1px solid #15181d; padding-bottom: 2pt; }
h3 { font-size: 8.5pt; margin: 7pt 0 3pt; color: #5b6472; }
h4 { font-size: 9pt; margin: 5pt 0 2pt; }
p { margin: 3pt 0; }
table { width: 100%; border-collapse: collapse; margin: 4pt 0; font-size: 7pt; }
th, td { border: 0.5px solid #c9cfd9; padding: 2pt 3pt; text-align: left; vertical-align: top; }
th { background: #f2f5f9; }
ul, ol { margin: 3pt 0 3pt 13pt; padding: 0; }
li { margin: 1.5pt 0; }
.sub, .evidence { font-size: 6.5pt; color: #5b6472; }
.callout { background: #f2f5f9; padding: 5pt 7pt; margin: 5pt 0; }
.badge { font-size: 6.5pt; font-weight: bold; }
.critical { color: #8b1a1a; } .high { color: #b3541e; } .medium { color: #8a6d1a; }
.low { color: #2c6e49; } .informational { color: #39506b; }
.stat { border: 0.5px solid #c9cfd9; padding: 3pt 5pt; }
.stat .n { display: block; font-size: 11pt; font-weight: bold; }
.stat .l { display: block; font-size: 6.5pt; color: #5b6472; }
.doc { border: 0.5px solid #c9cfd9; padding: 4pt 6pt; margin: 4pt 0; }
.masthead { border-bottom: 1.5px solid #15181d; padding-bottom: 6pt; }
footer { font-size: 6.5pt; color: #5b6472; margin-top: 10pt; }
"""


def _printable_body(html: str) -> str:
    """Strip the screen stylesheet and the document chrome, keep the content."""
    html = re.sub(r"<head>.*?</head>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    match = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.DOTALL | re.IGNORECASE)
    if match:
        html = match.group(1)
    # MuPDF selects one font per text run rather than falling back per glyph, so
    # a middot sitting inside a Kannada run has no glyph and prints as a box.
    html = html.replace("&middot;", " - ").replace("\u00b7", " - ")
    return "<div>" + html + "</div>"


def available() -> bool:
    return bool(kannada_font())


def render_pdf_kannada(html: str, out_path: Path, footer: str = "") -> Path:
    """Lay the report HTML out as a paginated PDF with correct Kannada shaping."""
    font = kannada_font()
    if not font:
        raise RuntimeError("No Kannada font is installed, so a Kannada PDF cannot be produced.")

    archive = fitz.Archive()
    archive.add(Path(font).read_bytes(), "kannada.ttf")
    archive.add(Path(latin_font() or font).read_bytes(), "latin.ttf")

    story = fitz.Story(html=_printable_body(html), user_css=PRINT_CSS, archive=archive)
    media = fitz.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
    content = fitz.Rect(MARGIN, MARGIN, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN - FOOTER_HEIGHT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = fitz.DocumentWriter(str(out_path))
    pages = 0
    more = 1
    while more:
        device = writer.begin_page(media)
        more, _filled = story.place(content)
        story.draw(device)
        writer.end_page()
        pages += 1
        if pages > 400:  # a guard against a layout that never converges
            log.warning("Kannada PDF stopped at %s pages", pages)
            break
    writer.close()

    _stamp_footers(out_path, footer)
    return out_path


def _stamp_footers(path: Path, footer: str) -> None:
    """Add a page footer. Only ASCII is drawn here, because the base fonts used
    for a raw text insert have no Kannada glyphs."""
    ascii_footer = "".join(ch for ch in footer if ord(ch) < 128).strip(" ·-")
    doc = fitz.open(str(path))
    try:
        for index, page in enumerate(doc, start=1):
            page.draw_line(fitz.Point(MARGIN, PAGE_HEIGHT - 30),
                           fitz.Point(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 30),
                           color=(0.79, 0.81, 0.85), width=0.4)
            page.insert_text(fitz.Point(MARGIN, PAGE_HEIGHT - 20), ascii_footer[:110],
                             fontsize=6.5, color=(0.36, 0.39, 0.45))
            page.insert_text(fitz.Point(PAGE_WIDTH - MARGIN - 40, PAGE_HEIGHT - 20),
                             "Page {} / {}".format(index, doc.page_count),
                             fontsize=6.5, color=(0.36, 0.39, 0.45))
        doc.saveIncr()
    finally:
        doc.close()
