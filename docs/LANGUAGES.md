# Languages — Kannada documents and the bilingual interface

Two separate things, often confused:

1. **Reading Kannada documents.** The analysis pipeline reads Kannada as well as English.
2. **Showing the system in Kannada.** The interface and the report render in either language.

Both work. What each one covers, and where it stops, is set out below.

---

## 1. Reading Kannada documents

Karnataka issues its own records in Kannada — Bhoomi RTC/Pahani, Kaveri encumbrance
certificates, mutation extracts, panchayat khata — and most registered deeds in rural
Karnataka are written in Kannada. These are read natively.

### What is handled

| | |
|---|---|
| **Classification** | 40 of the 58 document types carry Kannada vocabulary (`strong_kn` / `keywords_kn` in `backend/app/rules/doc_types.yaml`). ಕ್ರಯ ಪತ್ರ, ಪಹಣಿ, ಋಣಭಾರ ಪ್ರಮಾಣ ಪತ್ರ, ಅಡಮಾನ ಪತ್ರ, ಪಾಲು ಪತ್ರ, ಭೂ ಪರಿವರ್ತನೆ ಆದೇಶ, ಖಾತಾ ಪ್ರಮಾಣ ಪತ್ರ, ಮುಖ್ತ್ಯಾರ್ ಪತ್ರ and the rest |
| **Digits** | Kannada digits (೦–೯) are mapped to ASCII before any pattern runs, so `ಸರ್ವೇ ಸಂಖ್ಯೆ ೧೨೩/೪ಬಿ` reads as `123/4ಬಿ` |
| **Dates** | `೧೮/೦೬/೨೦೨೪` and `೧೨ ಮಾರ್ಚ್ ೨೦೧೫` — all twelve Kannada month names |
| **Extents** | ಎಕರೆ, ಗುಂಟೆ, ಸೆಂಟ್, ಹೆಕ್ಟೇರ್, ಚದರ ಅಡಿ, ಚದರ ಮೀಟರ್, ಅಂಕಣ — converted to square metres like their English equivalents, so `೨ ಎಕರೆ ೧೫ ಗುಂಟೆ` and `2 acres 15 guntas` compare exactly |
| **Money** | `ರೂ. ೪೫,೦೦,೦೦೦/-`, `೪೫ ಲಕ್ಷ`, `೧.೫ ಕೋಟಿ` |
| **Names** | Honorifics (ಶ್ರೀ, ಶ್ರೀಮತಿ, ದಿವಂಗತ) and relationship clauses (ಬಿನ್, ಕೋಂ, ತಂದೆ) are stripped, so `ಶ್ರೀಮತಿ ಲತಾ ರಾವ್ ಕೋಂ ಮೋಹನ್ ರಾವ್` matches `ಲತಾ ರಾವ್` |
| **Fields** | 42 Kannada patterns: ಸರ್ವೇ ಸಂಖ್ಯೆ, ಹಿಸ್ಸಾ, ಖಾತಾ ಸಂಖ್ಯೆ, ಗ್ರಾಮ, ಹೋಬಳಿ, ತಾಲ್ಲೂಕು, ಜಿಲ್ಲೆ, ಖಾತೆದಾರ, ಮಾರಾಟಗಾರ, ಖರೀದಿದಾರ, ಅಡಮಾನದಾರ, ವಿಸ್ತೀರ್ಣ, ಖರಾಬು, ಕ್ರಯದ ಮೊತ್ತ, ನೋಂದಣಿ ಸಂಖ್ಯೆ, ಅವಧಿ, ಚಕ್ಕುಬಂದಿ and the rest |
| **Signals** | Kannada vocabulary for mortgages (ಅಡಮಾನ, ಗಿರವಿ), releases (ಅಡಮಾನ ಬಿಡುಗಡೆ, ಸಾಲ ಮುಕ್ತಾಯ), litigation (ತಡೆಯಾಜ್ಞೆ, ವ್ಯಾಜ್ಯ, ಭೂ ಸ್ವಾಧೀನ), restrictions (ಪರಭಾರೆ ಮಾಡುವಂತಿಲ್ಲ, ಪಿಟಿಸಿಎಲ್, ಗೇಣಿ), and denials (`ಯಾವುದೇ ಋಣಭಾರ … ಇಲ್ಲ` is read as a covenant, not as a charge) |

**Mixed cases work.** An English sale deed and a Kannada RTC describing the same property
are cross-checked against each other: the extents are compared in square metres, the names
are matched across scripts, and a discrepancy between them is reported once, citing both.

### Scanned Kannada paper

A Kannada document with a real text layer — which is what Bhoomi and Kaveri produce —
needs no OCR. A **scanned** Kannada document does, and here the OCR engine matters:

| Engine | Kannada | Notes |
|---|---|---|
| Tesseract with the Kannada pack | **Yes** | The best reader of scanned documents, and the fastest |
| EasyOCR | **Yes** | `pip install easyocr`; runs a local neural model, several times slower per page |
| macOS Vision | **No.** Apple's engine supports English, Hindi and Marathi among Indic languages, but not Kannada | The best reader of photographs |

```bash
brew install tesseract tesseract-lang                  # macOS, with Homebrew
sudo apt-get install tesseract-ocr tesseract-ocr-kan   # Debian/Ubuntu
```

Without Homebrew and without an administrator password, conda-forge ships a
prebuilt Tesseract for Apple Silicon that installs into a private prefix:

```bash
mkdir -p ~/.local/share/dd-ocr && cd ~/.local/share/dd-ocr
curl -sL https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xj bin/micromamba
MAMBA_ROOT_PREFIX=$PWD/root ./bin/micromamba create -y -p ./env -c conda-forge tesseract
```

That build carries 125 languages, Kannada among them. Point the system at it with
`TESSERACT_CMD=~/.local/share/dd-ocr/env/bin/tesseract`, since it is not on `PATH`.

Then set `OCR_LANGUAGE=eng+kan` and restart. Tesseract takes precedence over macOS Vision
when both are present. Until then a scanned Kannada page is **flagged for manual review,
not guessed at** — the System page states which engine is live, and now also which of the
configured languages it can actually read.

### Which engine reads a given document

More than one engine is usually installed, and none of them is best at
everything: Tesseract reads a scanned deed better than macOS Vision, Vision
reads a phone photograph of a layout plan better than Tesseract, and only
Tesseract and EasyOCR read Kannada at all. The engine is therefore chosen per
document rather than fixed in configuration.

A few pages are sampled, spread through the file rather than taken from the
front, since a cover sheet is often in English on a document that is otherwise
Kannada. The sample settles two questions: whether the document is in a script
the preferred engine cannot read, and, among the engines that can read the
scripts actually present, which one reads these pages best — measured as how
much text it recovered weighted by how confident it was. The decision is made
once per document, so a four-hundred-page file costs the same to decide as a
one-page one, and the sampled pages are not read twice. When the choice falls to
anything other than the usual engine the report says so, naming the reason.

The check is made against the engine, not assumed from the setting. Setting `eng+kan` on a
machine where only macOS Vision is installed does not make Kannada readable: the engine
would silently fall back to English and render Kannada glyphs as Latin noise. Instead the
language is reported as unreadable, and every affected document carries an issue saying so.

### Text-layer quirks in Kaveri and Bhoomi PDFs

Kannada PDFs issued by the state portals carry a real text layer, but it is not clean. Two
defects appear in documents seen in practice, and both are repaired before any matching:

- **Control characters inside words.** A Kaveri encumbrance certificate renders the word
  `ನಮೂನೆ` ("form") with a `\x1f` wedged between the first two letters. Until these are
  removed the phrase never matches and the most common document type in Karnataka fails to
  classify at all. They are *deleted*, not replaced with a space, which would split the word.
- **A carriage return inside a word.** The same certificate splits `ಸಂಖ್ಯೆ` ("number") across
  a bare `\r`. These are only joined when the return follows a combining mark — a line can
  never begin where a vowel sign or anusvara left off — so genuine line breaks are kept.

A document whose text layer is too corrupt to repair (broken font encodings that map Kannada
to unrelated Latin letters) is still classified *Unknown*, as it should be: the text that was
extracted is not what the page says.

### What is not handled

- **Other Indian scripts.** Devanagari digits are mapped, but there is no Hindi, Tamil,
  Telugu or Marathi vocabulary. Such documents are classified as *Unknown — manual review
  required*.
- **Term coverage.** The Kannada vocabulary follows common Karnataka revenue and
  registration usage. Regional and older forms exist that it will not recognise. **It
  should be reviewed by a Kannada-speaking property professional** before the output is
  relied on; the terms are in one YAML file, deliberately separated from the English ones,
  so they can be reviewed and extended without touching code.

---

## 2. The bilingual interface

Switch with the **English / ಕನ್ನಡ** control in the header. The choice is remembered in the
browser and is sent to the API, so both the interface and the data come back in the chosen
language. A `kn` browser preference selects Kannada on first visit.

### Fully translated

- Every screen: navigation, tabs, buttons, table headings, form labels, empty states,
  prompts and the standing explanatory notes.
- Every controlled value: severities, statuses, categories, priorities, provenance,
  property types, transaction types, assessment statuses, field names.
- All 58 document type names.
- All 26 Karnataka requirement templates — name, reason, issuing authority, next action,
  risk of proceeding without it, and what closes it. This is the checklist a reviewer
  actually works from.
- Findings: title, consequence and recommended action, for 39 detector types.
- The report: all thirteen section headings, the standing text, the scope statement, the
  disclaimer and the final assessment.

### What stays in the document's own script, in either language

Three kinds of text are **never** translated, in either direction, and this is deliberate:

| | Why |
|---|---|
| Case details you typed — property name, owner, village, purpose | It is your data. Translating it would change what you wrote. |
| Values extracted from documents — survey numbers, names, extents, boundaries, land classification | The report must say what the document says. `123/4ಬಿ` is what the RTC reads; rendering it as `123/4B` would misquote the record. |
| Evidence quotations | A quotation that has been translated is no longer evidence. |

So with the interface in English, a case built from Kannada records still shows Kannada
survey numbers, owner names and quoted passages — and the reverse is true for English
documents with the interface in Kannada. The pages that show this kind of content carry a
one-line note saying so, because it would otherwise look like a translation failure.

### Shown in English, and marked as such

A finding's **detailed description** quotes the documents — filenames, extents, dates,
survey numbers, names — and is generated in English. It is shown with an **English** tag
next to it and a note explaining why, rather than being machine-mangled or dropped. The
evidence it cites is language-neutral and shown either way.

The same applies to **issue-driven requirements** — the ones generated from a finding
rather than from the jurisdiction template ("Obtain the loan closure / no-dues
certificate…"). Template requirements are fully translated; issue-driven ones are not, and
are marked.

Coverage is reported on the **System** page, including how many interface strings still
await Kannada. Nothing is silently half-translated.

### The Kannada PDF

ReportLab, which typesets the English PDF, performs no complex-script shaping: Kannada
conjuncts come out broken (`ಪ್ರಮಾಣ` renders as `ಪ್‌ರಮಾಣ`). The Kannada PDF is therefore laid
out through MuPDF's HTML engine, which shapes correctly, from the report's own HTML.

One consequence, worth knowing: **text copied or searched out of the Kannada PDF is
unreliable**, because shaped conjunct glyphs carry no reverse mapping to Unicode. The page
reads and prints correctly. When you need the text itself — to search, quote or paste —
use the HTML report, which is the machine-readable form.

A Kannada font must be present. macOS ships `NotoSansKannada.ttc`; on Linux install
`fonts-noto-kannada` or `fonts-lohit-knda`. Without one, the Kannada PDF endpoint returns
503 and says so; the Kannada HTML report still works, using the reader's own fonts.

---

## Extending the translations

| What | Where |
|---|---|
| Interface strings | `frontend/src/i18n/strings.ts` |
| Vocabularies, field names | `backend/app/i18n.py` |
| Document type names | `label_kn` in `backend/app/rules/doc_types.yaml` |
| Document vocabulary for classification | `strong_kn` / `keywords_kn`, same file |
| Field patterns | `KANNADA_LABEL_PATTERNS` in `backend/app/services/fields.py` |
| Requirement templates | `*_kn` keys in `backend/app/rules/jurisdictions/KA.yaml` |
| Finding titles and actions | `backend/app/services/findings_i18n.py` |
| Report headings | `backend/app/services/report_i18n.py` |

Adding a third language means adding a column to these catalogues and a code to
`i18n.LANGUAGES`; nothing in the analysis engine is English-specific.
