"""OCR backends.

Three engines are supported and tried in order:

1. **Tesseract**, when the binary is installed. Cross-platform, and the engine
   the documentation assumes.
2. **macOS Vision**, the recognition engine built into macOS, reached through
   the ``ocrmac`` bindings. Nothing to install at system level and no model
   download, and fast, but it reads no Kannada.
3. **EasyOCR**, a pip-installable engine with its own Kannada model. Much
   slower per page because it runs a neural model, so it is tried last — but it
   is the only one of the three that reads Kannada without a system-level
   install.

All three run entirely on this machine; no page is sent anywhere. The order is
deliberate: the engine that can read the configured languages is preferred over
one that would silently fall back to the wrong script. If none is present the
system says so and marks the document for manual review — it never guesses at
the contents of a page it could not read.
"""
from __future__ import annotations

import functools
import io
import os
import shutil
from typing import List, Optional, Tuple

#: Tesseract language code -> EasyOCR code. EasyOCR names most languages by
#: their ISO 639-1 code.
_EASYOCR_LANGUAGES = {
    "eng": "en", "kan": "kn", "hin": "hi", "tam": "ta", "tel": "te",
    "mar": "mr", "ben": "bn", "urd": "ur", "deu": "de", "fra": "fr",
    "spa": "es", "nep": "ne", "asm": "as",
}

#: Tesseract language code -> BCP-47 codes understood by macOS Vision.
_VISION_LANGUAGES = {
    "eng": ["en-US"],
    "kan": ["kn-IN"],
    "hin": ["hi-IN"],
    "tam": ["ta-IN"],
    "tel": ["te-IN"],
    "mar": ["mr-IN"],
    "guj": ["gu-IN"],
    "ben": ["bn-IN"],
    "mal": ["ml-IN"],
    "pan": ["pa-IN"],
    "urd": ["ur-IN"],
    "deu": ["de-DE"],
    "fra": ["fr-FR"],
    "spa": ["es-ES"],
}


#: Human names for the Tesseract codes, for messages the user reads.
_LANGUAGE_NAMES = {
    "eng": "English", "kan": "Kannada", "hin": "Hindi", "tam": "Tamil",
    "tel": "Telugu", "mar": "Marathi", "guj": "Gujarati", "ben": "Bengali",
    "mal": "Malayalam", "pan": "Punjabi", "urd": "Urdu", "deu": "German",
    "fra": "French", "spa": "Spanish",
}


def _configured_tesseract() -> Optional[str]:
    """An explicitly configured Tesseract binary, if it exists."""
    try:
        from ...config import get_settings

        configured = get_settings().tesseract_cmd
    except Exception:  # pragma: no cover - configuration optional here
        return None
    if not configured:
        return None
    path = os.path.expanduser(configured)
    return path if os.path.isfile(path) and os.access(path, os.X_OK) else None


@functools.lru_cache(maxsize=1)
def tesseract_available() -> bool:
    """Tesseract is preferred when present, including from a private prefix.

    ``TESSERACT_CMD`` points at a binary that is not on PATH, which is how it
    gets installed on a Mac without Homebrew.
    """
    try:
        import pytesseract
    except Exception:  # pragma: no cover - optional dependency
        return False

    configured = _configured_tesseract()
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured
        return True
    if shutil.which("tesseract"):
        return True
    cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    return bool(cmd and shutil.which(cmd))


@functools.lru_cache(maxsize=1)
def vision_available() -> bool:
    """macOS Vision, via the ocrmac bindings."""
    try:
        import platform

        if platform.system() != "Darwin":
            return False
        from ocrmac import ocrmac  # noqa: F401

        return True
    except Exception:  # pragma: no cover - platform dependent
        return False


@functools.lru_cache(maxsize=1)
def easyocr_available() -> bool:
    try:
        import easyocr  # noqa: F401

        return True
    except Exception:  # pragma: no cover - optional dependency
        return False


#: Tried in this order, cheapest first. EasyOCR is last because it loads a
#: neural model and is far slower per page; it is reached when it is the only
#: engine that can read the configured script, which on a Mac means Kannada.
_ENGINE_ORDER = (
    ("tesseract", tesseract_available),
    ("macos_vision", vision_available),
    ("easyocr", easyocr_available),
)


def installed_engines() -> List[str]:
    return [name for name, check in _ENGINE_ORDER if check()]


def _can_read(engine: str, language: str) -> bool:
    return not _missing_for(engine, language)


@functools.lru_cache(maxsize=16)
def engine_for(language: str) -> Optional[str]:
    """The engine used for these languages.

    The first installed engine that can read *all* of them wins, rather than
    simply the first installed engine: with Kannada configured, an engine that
    would quietly fall back to English is the wrong choice even when it is
    otherwise preferred. If none can read everything the usual order applies and
    the gap is reported instead of hidden.
    """
    available = installed_engines()
    for name in available:
        if _can_read(name, language):
            return name
    return available[0] if available else None


@functools.lru_cache(maxsize=1)
def active_engine() -> Optional[str]:
    return engine_for(_configured_language())


def _configured_language() -> str:
    try:
        from ...config import get_settings

        return get_settings().ocr_language or "eng"
    except Exception:  # pragma: no cover - configuration optional here
        return "eng"


def ocr_available() -> bool:
    return active_engine() is not None


def reset_engine_cache() -> None:
    """Pick up an engine installed while the process was running."""
    tesseract_available.cache_clear()
    vision_available.cache_clear()
    easyocr_available.cache_clear()
    active_engine.cache_clear()
    engine_for.cache_clear()
    _vision_supported.cache_clear()
    _missing_for.cache_clear()
    _easyocr_reader.cache_clear()


@functools.lru_cache(maxsize=1)
def _vision_supported() -> frozenset:
    """The BCP-47 codes this machine's Vision engine can actually recognise.

    Asked at runtime rather than assumed: macOS Vision reads no Kannada, and
    handing it an unsupported code makes it fall back to English, which turns a
    Kannada page into convincing-looking Latin noise instead of an error.
    """
    try:
        import Vision

        request = Vision.VNRecognizeTextRequest.alloc().init()
        found, _ = request.supportedRecognitionLanguagesAndReturnError_(None)
        return frozenset(str(code) for code in (found or []))
    except Exception:  # pragma: no cover - platform dependent
        return frozenset()


def requested_languages(language: str) -> List[str]:
    """The Tesseract-style codes in an ``eng+kan`` setting."""
    return [part.strip() for part in (language or "eng").split("+") if part.strip()]


@functools.lru_cache(maxsize=32)
def _missing_for(engine: Optional[str], language: str) -> tuple:
    """Which of the requested languages a given engine cannot read."""
    wanted = requested_languages(language)
    if engine == "tesseract":
        try:
            import pytesseract

            installed = set(pytesseract.get_languages(config=""))
        except Exception:  # pragma: no cover - environment dependent
            return tuple()
        return tuple(code for code in wanted if code not in installed)
    if engine == "easyocr":
        return tuple(code for code in wanted if code not in _EASYOCR_LANGUAGES)
    if engine == "macos_vision":
        supported = _vision_supported()
        if not supported:  # could not ask; do not invent a warning
            return tuple()
        return tuple(
            code for code in wanted
            if not any(c in supported for c in _VISION_LANGUAGES.get(code, []))
        )
    return tuple()


def unreadable_languages(language: str) -> tuple:
    """Which of the requested languages the chosen engine cannot read.

    Reported rather than silently dropped: a document in a script the engine
    does not know is one the system has not read, and saying otherwise would be
    a false assurance about the contents.
    """
    return _missing_for(engine_for(language), language)


def _language_warning(language: str) -> Optional[str]:
    missing = unreadable_languages(language)
    if not missing:
        return None
    names = ", ".join(_LANGUAGE_NAMES.get(code, code) for code in missing)
    engine = ENGINE_LABELS.get(active_engine(), "the OCR engine")
    return (
        "{} cannot read {}; any text in that script has not been read and needs manual "
        "review. Install Tesseract with the matching language pack to read it "
        "(macOS: `brew install tesseract tesseract-lang`).".format(engine, names)
    )


def _vision_languages(language: str) -> List[str]:
    """Only the codes Vision actually supports, so it is not pushed into a
    silent English fallback."""
    supported = _vision_supported()
    out: List[str] = []
    for part in requested_languages(language):
        for code in _VISION_LANGUAGES.get(part, []):
            if not supported or code in supported:
                out.append(code)
    return out or ["en-US"]


#: Unicode ranges for the scripts an engine may be unable to read, used to ask
#: "did the other engine actually find this script on the page?"
_SCRIPT_RANGES = {
    "kan": ("\u0c80", "\u0cff"),
    "hin": ("\u0900", "\u097f"),
    "mar": ("\u0900", "\u097f"),
    "tam": ("\u0b80", "\u0bff"),
    "tel": ("\u0c00", "\u0c7f"),
    "ben": ("\u0980", "\u09ff"),
    "guj": ("\u0a80", "\u0aff"),
    "mal": ("\u0d00", "\u0d7f"),
    "pan": ("\u0a00", "\u0a7f"),
}

#: A page is taken to be in a script once a quarter of its letters are in it.
#: Well clear of the stray characters a recogniser invents on a page that is
#: not in that script at all.
_SCRIPT_SHARE = 0.25


def engine_candidates(language: str) -> List[str]:
    """The engines worth trying for a document, cheapest first.

    Two only when the cheap engine cannot read everything configured and
    another installed engine can. Then the page itself has to settle which is
    right, because a Kannada page and an English one look the same until one of
    them is read.
    """
    available = installed_engines()
    if not available:
        return []
    first = available[0]
    if _can_read(first, language):
        return [first]
    capable = next((name for name in available if _can_read(name, language)), None)
    return [first, capable] if capable else [first]


def script_share(text: str, language: str, engine: str) -> float:
    """How much of the text is in a script this engine cannot read."""
    missing = _missing_for(engine, language)
    ranges = [_SCRIPT_RANGES[code] for code in missing if code in _SCRIPT_RANGES]
    if not ranges or not text:
        return 0.0
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    found = sum(1 for ch in letters if any(lo <= ch <= hi for lo, hi in ranges))
    return found / len(letters)


#: Below this many characters a sample page counts as unread.
_BLANK_SAMPLE_CHARS = 10

#: Engines too slow to run just to compare quality. EasyOCR runs a neural model
#: and is reached on the strength of the script it can read, not by trial.
_SLOW_ENGINES = {"easyocr"}


def _sample_score(reads: dict) -> float:
    """How well an engine read the sample: how much it read, times how sure.

    Both halves are needed. Confidence alone prefers an engine that confidently
    reads a caption and misses the rest of the page; volume alone prefers one
    that fills the page with noise.
    """
    total = sum(len(text.strip()) for text, _ in reads.values())
    if not total:
        return 0.0
    return sum(len(text.strip()) * confidence for text, confidence in reads.values())


def _read_samples(samples: List[bytes], language: str, engine: str) -> dict:
    reads = {}
    for position, data in enumerate(samples):
        text, confidence, _ = ocr_image_bytes(data, language, engine=engine)
        reads[position] = (text, confidence)
    return reads


def _anything_read(reads: dict) -> bool:
    return any(len(text.strip()) >= _BLANK_SAMPLE_CHARS for text, _ in reads.values())


def _joined(reads: dict) -> str:
    return "\n".join(text for text, _ in reads.values())


def scripts_present(text: str, language: str) -> List[str]:
    """Which of the configured scripts actually appear on the page.

    What is configured is a superset of what any one document contains: a case
    may be set to read Kannada and English while this particular deed is wholly
    in English. Judging an engine on a script that is not there would rule out
    the engine that reads the page best.
    """
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return []
    found = []
    for code in requested_languages(language):
        bounds = _SCRIPT_RANGES.get(code)
        if not bounds:
            continue
        lo, hi = bounds
        share = sum(1 for ch in letters if lo <= ch <= hi) / len(letters)
        if share >= _SCRIPT_SHARE:
            found.append(code)
    return found


def choose_engine(samples: List[bytes], language: str) -> Tuple[Optional[str], Optional[str], dict]:
    """Pick one engine for a whole document by reading a few of its pages.

    Two things can go wrong, and the sample settles both. The preferred engine
    may not read the script the document is written in; or it may read it, but
    another engine reads this particular page far better - Tesseract is the
    better reader of a scanned deed, macOS Vision of a phone photograph, and
    neither order is right for every document.

    Returns ``(engine, note, reads)``, where ``reads`` maps the position of a
    sample to the ``(text, confidence)`` already obtained for it, so a sampled
    page is not read twice. Deciding once per document rather than per page
    keeps the cost flat on a long file.
    """
    ordered = engine_candidates(language)
    ordered += [name for name in installed_engines() if name not in ordered]
    if not ordered:
        return (None, None, {})
    if len(ordered) == 1 or not samples:
        return (ordered[0], None, {})

    preferred = ordered[0]
    capable = next((name for name in ordered if _can_read(name, language)), preferred)

    # The preferred engine cannot read everything configured, so it cannot be
    # asked what script the page is in - only an engine that reads that script
    # can answer, and its answer decides.
    if capable != preferred:
        reads = _read_samples(samples, language, capable)
        shares = [script_share(text, language, preferred) for text, _ in reads.values()]
        if shares and max(shares) >= _SCRIPT_SHARE:
            missing = ", ".join(_LANGUAGE_NAMES.get(c, c) for c in _missing_for(preferred, language))
            return (capable, "Read with {} because the document is in {}.".format(
                ENGINE_LABELS.get(capable, capable), missing), reads)

    # Otherwise the preferred engine reads the configured scripts, so its own
    # reading shows which of them this document actually uses.
    reads = _read_samples(samples, language, preferred)
    present = "+".join(scripts_present(_joined(reads), language)) or "eng"
    contenders = [name for name in ordered
                  if name not in _SLOW_ENGINES and not _missing_for(name, present)]
    if len(contenders) > 1:
        scored = {preferred: (_sample_score(reads), reads)}
        for engine in contenders:
            if engine not in scored:
                other = _read_samples(samples, language, engine)
                scored[engine] = (_sample_score(other), other)
        best = max(scored, key=lambda name: scored[name][0])
        score, reads = scored[best]
        if score > 0:
            if best == preferred:
                return (best, None, reads)
            return (best, "Read with {} because it read this document better than {}.".format(
                ENGINE_LABELS.get(best, best),
                ENGINE_LABELS.get(preferred, preferred)), reads)
    elif _anything_read(reads):
        return (preferred, None, reads)

    # Nothing legible from those, so fall back to any engine that reads at all.
    for engine in ordered:
        found = _read_samples(samples, language, engine)
        if _anything_read(found):
            if engine == preferred:
                return (engine, None, found)
            return (engine, "Read with {} because {} returned no text for this document.".format(
                ENGINE_LABELS.get(engine, engine),
                ENGINE_LABELS.get(preferred, preferred)), found)
    return (preferred, None, {})


def ocr_image_bytes(data: bytes, language: str = "eng",
                    engine: Optional[str] = None) -> Tuple[str, float, Optional[str]]:
    """Return ``(text, confidence, error)`` for a raster image.

    ``engine`` overrides the automatic choice, so a document that has already
    been probed is read with the engine that probe settled on.
    """
    engine = engine or engine_for(language)
    if engine is None:
        return ("", 0.0, "No OCR engine is available on this machine")
    if engine == "tesseract":
        return _ocr_tesseract(data, language)
    if engine == "easyocr":
        return _ocr_easyocr(data, language)
    return _ocr_vision(data, language)


def _ocr_tesseract(data: bytes, language: str) -> Tuple[str, float, Optional[str]]:
    """Line structure is rebuilt from the word boxes.

    The page-level patterns match a label against the value on its own line, so
    joining every word with spaces - as a plain ``image_to_string`` effectively
    does here - would run the whole page together and lose them.
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(data))
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        found = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT)

        lines, confs = {}, []
        for index, word in enumerate(found.get("text", [])):
            if not word or not word.strip():
                continue
            key = (found["block_num"][index], found["par_num"][index], found["line_num"][index])
            lines.setdefault(key, []).append(word)
            try:
                value = float(found["conf"][index])
            except (TypeError, ValueError):
                value = -1.0
            if value >= 0:
                confs.append(value / 100.0)

        text = "\n".join(" ".join(words) for _, words in sorted(lines.items()))
        confidence = round(sum(confs) / len(confs), 3) if confs else 0.0
        return (text, confidence, _language_warning(language))
    except Exception as exc:  # pragma: no cover - environment dependent
        return ("", 0.0, "OCR failed (tesseract): {}".format(exc))


def _easyocr_codes(language: str) -> List[str]:
    """EasyOCR codes for the request, English last.

    EasyOCR will not load two scripts that use different recognition models at
    once, so an unsupported pairing is reduced to the non-Latin script plus
    English, which is the combination Karnataka documents actually need.
    """
    codes = []
    for part in requested_languages(language):
        code = _EASYOCR_LANGUAGES.get(part)
        if code and code not in codes:
            codes.append(code)
    scripts = [code for code in codes if code != "en"]
    if not scripts:
        return ["en"]
    # One non-Latin script at a time, English last: English shares a model with
    # every script, but two Indic scripts together do not.
    return [scripts[0]] + (["en"] if "en" in codes else [])


@functools.lru_cache(maxsize=4)
def _easyocr_reader(codes: tuple):
    """One reader per language set; building it loads a neural model."""
    import easyocr

    return easyocr.Reader(list(codes), gpu=False, verbose=False)


def _ocr_easyocr(data: bytes, language: str) -> Tuple[str, float, Optional[str]]:
    """EasyOCR reads Kannada, which is why it is here.

    The first call downloads the detection and recognition models (about
    100 MB) to ``~/.EasyOCR``; afterwards everything is local and offline.
    """
    try:
        import numpy
        from PIL import Image

        image = Image.open(io.BytesIO(data))
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        reader = _easyocr_reader(tuple(_easyocr_codes(language)))
        found = reader.readtext(numpy.array(image), detail=1, paragraph=False)
        if not found:
            return ("", 0.0, _language_warning(language))

        # EasyOCR returns (box, text, confidence) with the box in image
        # coordinates, origin top-left. Grouping by row keeps lines apart, which
        # the page-level patterns rely on.
        def top(item):
            box = item[0]
            return min(point[1] for point in box)

        def left(item):
            box = item[0]
            return min(point[0] for point in box)

        ordered = sorted(found, key=lambda i: (round(top(i) / 12.0), left(i)))
        lines, current, row = [], [], None
        for item in ordered:
            band = round(top(item) / 12.0)
            if row is not None and band != row:
                lines.append(" ".join(current))
                current = []
            current.append(item[1])
            row = band
        if current:
            lines.append(" ".join(current))

        text = "\n".join(line for line in lines if line.strip())
        confs = [float(i[2]) for i in found if len(i) > 2 and i[2] is not None]
        confidence = round(sum(confs) / len(confs), 3) if confs else 0.0
        return (text, confidence, _language_warning(language))
    except Exception as exc:  # pragma: no cover - environment dependent
        return ("", 0.0, "OCR failed (EasyOCR): {}".format(exc))


def _ocr_vision(data: bytes, language: str) -> Tuple[str, float, Optional[str]]:
    """macOS Vision keeps line structure, which the page-level patterns rely on."""
    try:
        from ocrmac import ocrmac
        from PIL import Image

        image = Image.open(io.BytesIO(data))
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        results = ocrmac.OCR(
            image, recognition_level="accurate", language_preference=_vision_languages(language)
        ).recognize()
        if not results:
            return ("", 0.0, _language_warning(language))

        # Vision returns (text, confidence, bbox) with the bbox in normalised
        # coordinates whose origin is bottom-left. Sorting by descending y then
        # ascending x restores reading order and keeps lines separate.
        def position(item):
            bbox = item[2] if len(item) > 2 and item[2] else (0, 0, 0, 0)
            x, y = bbox[0], bbox[1]
            return (-round(y, 3), round(x, 3))

        ordered = sorted(results, key=position)
        text = "\n".join(item[0] for item in ordered if item[0])
        confs = [float(item[1]) for item in ordered if len(item) > 1 and item[1] is not None]
        confidence = round(sum(confs) / len(confs), 3) if confs else 0.0
        return (text, confidence, _language_warning(language))
    except Exception as exc:  # pragma: no cover - environment dependent
        return ("", 0.0, "OCR failed (macOS Vision): {}".format(exc))


ENGINE_LABELS = {
    "tesseract": "Tesseract",
    "easyocr": "EasyOCR",
    "macos_vision": "macOS Vision (built in)",
}

_INSTALL_HINT = (
    "No OCR engine is available, so scanned and image-based documents are flagged for manual "
    "review instead of being read. Install Tesseract (macOS: `brew install tesseract`; "
    "Debian/Ubuntu: `apt-get install tesseract-ocr`), or install a Python engine into the "
    "virtual environment with `pip install easyocr` (reads Kannada) or, on macOS, "
    "`pip install ocrmac` for the built-in Vision engine."
)


def ocr_status(language: Optional[str] = None) -> dict:
    """What the OCR engine is, and which of the configured languages it can read.

    The language part matters: macOS Vision reads no Indic script except Hindi
    and Marathi, so a Karnataka deployment that assumes `eng+kan` works would be
    told it had read documents that were never read.
    """
    if language is None:
        language = _configured_language()
    engine = engine_for(language)
    wanted = requested_languages(language)
    missing = list(unreadable_languages(language))
    readable = [code for code in wanted if code not in missing]
    label = lambda codes: ", ".join(_LANGUAGE_NAMES.get(c, c) for c in codes)

    if engine is None:
        note = _INSTALL_HINT
    elif missing:
        note = ("Scanned documents are read with {}, which cannot read {}. Pages in that "
                "script are not read and are flagged for manual review; install Tesseract "
                "with the matching language pack to read them.".format(
                    ENGINE_LABELS.get(engine, engine), label(missing)))
    elif engine == "tesseract":
        note = ("Scanned documents are read with Tesseract ({}). Add languages with "
                "OCR_LANGUAGE, for example `eng+kan`.".format(label(readable)))
    elif engine == "easyocr":
        note = ("Scanned documents are read with EasyOCR ({}), which runs a local neural "
                "model - slower per page than the alternatives, and chosen here because it "
                "is the only installed engine that reads every configured script. Nothing is "
                "sent off the machine.".format(label(readable)))
    else:
        note = ("Scanned documents are read with the recognition engine built into macOS ({}). "
                "Nothing is sent off the machine.".format(label(readable)))
    return {
        "engine": ENGINE_LABELS.get(engine, "none"),
        "engine_key": engine,
        "available": engine is not None,
        "alternatives": {
            "tesseract": tesseract_available(),
            "macos_vision": vision_available(),
            "easyocr": easyocr_available(),
        },
        "languages": {
            "configured": wanted,
            "readable": readable,
            "unreadable": missing,
        },
        "note": note,
    }
