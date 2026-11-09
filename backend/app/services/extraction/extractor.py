"""Format dispatch for text extraction."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .base import ExtractionResult, PageText, sanitise_text
from .ocr import choose_engine, ocr_available, ocr_image_bytes


def extract_document(
    path: Path,
    ocr_enabled: bool = True,
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
    ocr_min_chars: int = 120,
    max_pages: int = 0,
) -> ExtractionResult:
    result = _extract(path, ocr_enabled, ocr_language, ocr_dpi, ocr_min_chars, max_pages)
    # One place to clean every format: producers embed control and zero-width
    # characters that would otherwise break phrase matching downstream.
    for page in result.pages:
        page.text = sanitise_text(page.text)
    result.issues = _collapse_per_page_issues(result.issues)
    return result


_PAGE_PREFIX = re.compile(r"^Page (\d+): ")


def _collapse_per_page_issues(issues: List[str]) -> List[str]:
    """Report a problem affecting many pages once, naming the pages.

    An engine that cannot read a script says so on every page of a 400-page
    scan; repeated verbatim that buries every other issue in the report.
    """
    order: List[str] = []
    pages: dict = {}
    for issue in issues:
        match = _PAGE_PREFIX.match(issue)
        body = issue[match.end():] if match else issue
        if body not in pages:
            order.append(body)
            pages[body] = []
        if match:
            pages[body].append(int(match.group(1)))
    out = []
    for body in order:
        found = pages[body]
        if not found:
            out.append(body)
        elif len(found) == 1:
            out.append("Page {}: {}".format(found[0], body))
        else:
            out.append("Pages {}: {}".format(_summarise_pages(found), body))
    return out


def _summarise_pages(numbers: List[int]) -> str:
    """``1-4`` rather than ``1, 2, 3, 4``; the first few when there are many."""
    runs = []
    for number in sorted(set(numbers)):
        if runs and number == runs[-1][1] + 1:
            runs[-1][1] = number
        else:
            runs.append([number, number])
    parts = ["{}-{}".format(a, b) if a != b else str(a) for a, b in runs]
    if len(parts) > 5:
        return "{} and {} more".format(", ".join(parts[:5]), len(parts) - 5)
    return ", ".join(parts)


def _extract(path: Path, ocr_enabled: bool, ocr_language: str, ocr_dpi: int,
             ocr_min_chars: int, max_pages: int) -> ExtractionResult:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return _extract_pdf(path, ocr_enabled, ocr_language, ocr_dpi, ocr_min_chars, max_pages)
        if ext == ".docx":
            return _extract_docx(path)
        if ext in (".txt", ".md"):
            return _extract_text(path)
        if ext in (".rtf", ".doc"):
            return _extract_legacy_word(path)
        if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"):
            return _extract_image(path, ocr_enabled, ocr_language)
    except Exception as exc:  # pragma: no cover - defensive
        return ExtractionResult(ok=False, error="Extraction failed: {}".format(exc), method="error")
    return ExtractionResult(ok=False, error="No extractor for '{}'".format(ext), method="none")


# ---------------------------------------------------------------------------
#: A page with fewer characters than this is treated as having no text at all -
#: an image inserted into an otherwise digital document, for instance.
EMPTY_PAGE_CHARS = 20


#: How many pages are read to decide which engine suits the document.
ENGINE_SAMPLE_PAGES = 2


def _sample_pages(candidates: List[int]) -> List[int]:
    """A few pages spread through the document, not just the first.

    A cover sheet is often in English on a document that is otherwise Kannada,
    so sampling only page one would pick the wrong engine for the whole file.
    """
    if len(candidates) <= ENGINE_SAMPLE_PAGES:
        return candidates
    step = len(candidates) / float(ENGINE_SAMPLE_PAGES + 1)
    picked = []
    for n in range(1, ENGINE_SAMPLE_PAGES + 1):
        index = candidates[min(int(step * n), len(candidates) - 1)]
        if index not in picked:
            picked.append(index)
    return picked


def _document_reads_as_a_scan(native_texts, ocr_min_chars: int) -> bool:
    """Decide once, for the whole document, whether it is a scan.

    Deciding page by page is wrong in both directions. A digital document with a
    few thin pages - a schedule heading, a signature page - would have each of
    them rasterised and OCR'd for nothing, which on a long document is minutes of
    wasted work. A scanned document carrying a digital registry stamp on every
    page would look as though it has text and be skipped, losing the content.

    Averaging across the document separates the two: a genuinely digital document
    clears the threshold comfortably, a stamped scan does not.
    """
    if not native_texts:
        return False
    total = sum(len(t.strip()) for t in native_texts)
    return (total / float(len(native_texts))) < ocr_min_chars


def _extract_pdf(path, ocr_enabled, lang, dpi, ocr_min_chars, max_pages) -> ExtractionResult:
    import fitz  # PyMuPDF

    result = ExtractionResult(method="pdf_text")
    ocr_attempted = False
    doc = fitz.open(str(path))
    try:
        if doc.is_encrypted and not doc.authenticate(""):
            return ExtractionResult(
                ok=False,
                method="pdf_encrypted",
                error="The PDF is password protected and cannot be read.",
                issues=["Password-protected PDF - a decrypted copy is required."],
            )
        total = doc.page_count
        # max_pages of 0 means read the whole document, however long it is.
        limit = total if not max_pages or max_pages <= 0 else min(total, max_pages)
        if limit < total:
            result.issues.append(
                "Document has {} pages; only the first {} were processed. Raise "
                "MAX_PAGES_PER_DOCUMENT, or set it to 0 to read the whole document.".format(
                    total, limit)
            )
        native = [(doc.load_page(i).get_text("text") or "") for i in range(limit)]
        scanned_document = _document_reads_as_a_scan(native, ocr_min_chars)

        engine, already_read = None, {}
        if ocr_enabled and ocr_available():
            needs_ocr = [i for i in range(limit)
                         if len(native[i].strip()) < EMPTY_PAGE_CHARS
                         or (scanned_document and len(native[i].strip()) < ocr_min_chars)]
            if needs_ocr:
                sampled = _sample_pages(needs_ocr)
                engine, note, reads = choose_engine(
                    [doc.load_page(i).get_pixmap(dpi=dpi).tobytes("png") for i in sampled], lang)
                already_read = {sampled[position]: value for position, value in reads.items()}
                if note:
                    result.issues.append(note)

        for index in range(limit):
            page = doc.load_page(index)
            text = native[index]
            ocr_used = False
            confidence = 1.0 if text.strip() else 0.0
            # An empty page is OCR'd whatever the document looks like; a merely
            # thin page only when the document as a whole reads as a scan.
            stripped = len(text.strip())
            if stripped < EMPTY_PAGE_CHARS or (scanned_document and stripped < ocr_min_chars):
                if ocr_enabled and ocr_available():
                    ocr_attempted = True
                    err = None
                    if index in already_read:
                        ocr_text, ocr_conf = already_read[index]
                    else:
                        pix = page.get_pixmap(dpi=dpi)
                        ocr_text, ocr_conf, err = ocr_image_bytes(pix.tobytes("png"), lang,
                                                                  engine=engine)
                    if err:
                        result.issues.append("Page {}: {}".format(index + 1, err))
                    if len(ocr_text.strip()) > len(text.strip()):
                        text, confidence, ocr_used = ocr_text, ocr_conf, True
                        result.ocr_used = True
                        result.method = "pdf_text+ocr"
                elif ocr_enabled:
                    result.issues.append(
                        "Page {} contains little or no selectable text and OCR is unavailable; "
                        "it requires manual review.".format(index + 1)
                    )
                    confidence = 0.0
            result.pages.append(
                PageText(page_no=index + 1, text=text.strip(), ocr_used=ocr_used, confidence=confidence)
            )
    finally:
        doc.close()

    if not result.text.strip():
        result.ok = False
        result.error = _no_text_reason(ocr_enabled, ocr_attempted)
    return result


def _no_text_reason(ocr_enabled: bool, ocr_attempted: bool) -> str:
    """Say precisely why nothing was read - the three cases need different action."""
    if ocr_attempted:
        return ("No text could be extracted. The document is a scanned image, OCR ran over it and "
                "recovered nothing: the page is blank, or the scan is too poor to read. A clearer "
                "copy is required.")
    if not ocr_enabled:
        return ("No text could be extracted. The document is a scanned image and OCR is disabled "
                "in the configuration.")
    return ("No text could be extracted. The document is a scanned image and no OCR engine is "
            "available on this machine, so its contents were not read.")


def _extract_docx(path) -> ExtractionResult:
    import docx

    document = docx.Document(str(path))
    chunks = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                chunks.append(" | ".join(cells))
    text = "\n".join(chunks)
    # DOCX has no fixed pagination; split into readable blocks for citation.
    pages = _paginate(text)
    result = ExtractionResult(pages=pages, method="docx")
    if not text.strip():
        result.ok = False
        result.error = "The DOCX file contains no readable text."
    else:
        result.issues.append(
            "DOCX files have no fixed pagination; page references are approximate text blocks."
        )
    return result


def _extract_text(path) -> ExtractionResult:
    raw = path.read_text(encoding="utf-8", errors="replace")
    result = ExtractionResult(pages=_paginate(raw), method="plaintext")
    if not raw.strip():
        result.ok = False
        result.error = "The file is empty."
    return result


def _extract_legacy_word(path) -> ExtractionResult:
    """Best-effort for .doc / .rtf without external converters."""
    raw = path.read_bytes()
    if raw[:5] == b"{\\rtf":
        import re

        text = raw.decode("latin-1", "replace")
        text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
        text = text.replace("{", " ").replace("}", " ")
        text = re.sub(r"[ \t]+", " ", text)
        result = ExtractionResult(pages=_paginate(text), method="rtf")
        result.issues.append("RTF parsed without a dedicated converter; formatting-dependent text may be lost.")
        if not text.strip():
            result.ok = False
            result.error = "No readable text in the RTF file."
        return result

    # Legacy binary .doc: extract printable runs, then insist on manual review.
    import re

    text = raw.decode("latin-1", "replace")
    candidates = re.findall(r"[ -~\n]{25,}", text)
    body = "\n".join(candidates)
    result = ExtractionResult(pages=_paginate(body), method="doc_salvage")
    result.issues.append(
        "Legacy .doc format: only a best-effort text salvage was possible. "
        "Convert the file to PDF or DOCX and re-add it for a reliable reading."
    )
    if len(body.strip()) < 200:
        result.ok = False
        result.error = "Legacy .doc file could not be read reliably; please supply a PDF or DOCX copy."
    return result


def _extract_image(path, ocr_enabled, lang) -> ExtractionResult:
    data = path.read_bytes()
    if not ocr_enabled:
        return ExtractionResult(
            ok=False, method="image", error="OCR is disabled; image documents cannot be read.",
            issues=["OCR disabled in configuration."],
        )
    # The image is its own sample: the probe reads it once to settle the engine,
    # and the result of that read is reused rather than repeated.
    engine, note, reads = choose_engine([data], lang)
    if 0 in reads:
        (text, conf), err = reads[0], None
    else:
        text, conf, err = ocr_image_bytes(data, lang, engine=engine)
    result = ExtractionResult(
        pages=[PageText(page_no=1, text=text.strip(), ocr_used=True, confidence=conf)],
        method="image_ocr",
        ocr_used=True,
    )
    if note:
        result.issues.append(note)
    if err:
        result.issues.append(err)
    if not text.strip():
        result.ok = False
        result.error = err or "OCR produced no text from the image; a clearer copy is required."
    elif conf < 0.6:
        result.issues.append(
            "OCR confidence is low ({:.0%}); extracted values should be verified against the original.".format(conf)
        )
    return result


def _paginate(text: str, chars_per_page: int = 3000):
    """Split unpaginated text into stable blocks so citations stay meaningful."""
    text = (text or "").strip()
    if not text:
        return []
    pages, buf, size, page_no = [], [], 0, 1
    for para in text.split("\n"):
        buf.append(para)
        size += len(para) + 1
        if size >= chars_per_page:
            pages.append(PageText(page_no=page_no, text="\n".join(buf).strip(), confidence=1.0))
            page_no += 1
            buf, size = [], 0
    if buf:
        pages.append(PageText(page_no=page_no, text="\n".join(buf).strip(), confidence=1.0))
    return pages
