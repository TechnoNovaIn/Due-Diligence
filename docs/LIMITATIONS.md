# Limitations — what this system can and cannot establish

Read this before relying on a report.

## What it actually does

It reads the documents you place in a folder, extracts what they say, compares them with
each other, and records what is inconsistent, unsupported or absent. Every statement it
makes is about **the supplied documents**.

## What it cannot do

**It cannot see what you did not give it.** No finding about a document that was never
supplied, a charge that was never registered, or a dispute nobody disclosed. The absence of
a finding is never evidence that the underlying issue does not exist, and every report says
so explicitly.

**It does not check any official record.** No Sub-Registrar record, no Bhoomi or municipal
database, no court registry, no RERA portal, no acquisition notification has been searched.
A scanned deed has not been matched against the register — the system cannot tell a
genuine certified copy from a fabricated one, and never claims to.

**It does not determine authenticity.** It reports observable concerns — missing pages, a
referenced annexure that is not present, a registration date before the execution date,
low OCR confidence, text addressed to an automated system. These are observations requiring
independent verification, not conclusions about forgery, and the report labels them that
way.

**It does not give a legal opinion.** It does not decide whether title is marketable,
whether a transfer was validly executed, whether a restriction applies, or whether a
transaction should proceed. Those are questions for a qualified property lawyer.

**It does not confirm possession or physical extent.** Boundaries, encroachment, access and
actual measurement can only be established on site.

## Specific things the report is careful about

| The system will not say | Because |
|---|---|
| "Ownership is verified" | Names matching across documents is not proof the same person is involved, nor that each transfer was valid. The report says *documented* or *corroborated*. |
| "There is no litigation" | No court record was searched. The report says no litigation reference was found **in the supplied documents**. |
| "The property is free from encumbrances" | An Encumbrance Certificate covers only what was registered, only for the period certified, and only against the identifiers used. An equitable mortgage by deposit of title deeds frequently does not appear at all. |
| "The documents are genuine" | Authenticity cannot be determined from a scan. |
| "The property is safe to purchase" | That is a legal and commercial judgement, not a document-comparison result. |

A revenue record (RTC, khata, tax receipt) evidences possession and who is assessed for
tax. It is **not** conclusive evidence of title, and the report states this wherever such a
document contributes to a finding.

## Jurisdiction rules

The requirement templates in `backend/app/rules/jurisdictions/` encode customary Karnataka
practice — a 30-year title search, 30-year EC coverage, mutation records reconciling each
transfer, DC conversion for non-agricultural use, khata and approved plans for built
property, and so on. They are marked `jurisdiction_confirmed: false` and every requirement
is labelled *jurisdiction not confirmed* in the interface and the report.

Statutory requirements change, vary by local body, and depend on facts the system cannot
see. **Confirm the checklist with a lawyer practising in the relevant jurisdiction**, and
edit the YAML to match. The same applies with more force to `DEFAULT.yaml`, which is a
generic starting point for states other than Karnataka.

The system does not assume a single checklist fits every property. What it asks for depends
on the property type, the transaction type, the ownership history and what the analysis
discovered — but the underlying template still needs professional confirmation.

## Extraction accuracy

Field extraction is pattern-based and tolerant, not perfect. It can mis-read an unusual
layout, a poor scan or an unfamiliar phrasing. Three safeguards:

1. Every extracted value shows the page and the sentence it came from, so it can be checked
   in seconds.
2. Any value can be corrected in the document viewer; corrections survive reprocessing and
   are recorded in the audit trail.
3. Documents whose type cannot be determined with confidence are marked *Unknown — manual
   review required* rather than guessed at, and a document that could not be read produces
   no extracted fields at all.

With no OCR engine available, scanned documents and images are **not read**. They are
flagged for manual review and reported as not assessed; nothing is inferred about their
contents. With an engine available the text is recovered, but OCR output on a poor scan
can still be wrong — pages read below 60% confidence raise a finding telling you to check
the values against the original.

## Language

English and Kannada are both read, including Kannada digits, dates, extents, money and
names, and a case may mix the two. See [LANGUAGES.md](LANGUAGES.md) for exactly what is
covered.

Three limits are worth stating plainly:

- **The Kannada vocabulary has not been reviewed by a Kannada-speaking property
  professional.** It follows common Karnataka revenue and registration usage, but regional
  and older forms exist that it will not recognise. Have it checked before relying on the
  output; the terms sit in one YAML file, separate from the English ones, for that purpose.
- **Scanned Kannada paper needs Tesseract with the Kannada pack.** macOS Vision — the
  default OCR engine on a Mac — does not support Kannada. Without it, a scanned Kannada
  page is flagged for manual review rather than guessed at.
- **Other Indian scripts are not supported.** Hindi, Tamil, Telugu and Marathi documents
  are classified as *Unknown — manual review required*.

In the interface and the report, a finding's detailed description quotes the documents and
is generated in English; it is shown with an **English** marker rather than being
mistranslated. Everything else — the checklist, the finding titles and actions, the
report's structure, the scope statement and the disclaimer — is translated.

## Model assistance

With a language model configured, it adds narrative summaries, helps classify when the
rules are uncertain, and takes one open-ended look at the extracted evidence. It cannot
override a deterministic finding, its observations are marked unconfirmed, and its
confidence is capped. Everything above still applies: the model sees the same documents
and knows nothing about the official record either.

## The bottom line

The system is an evidence-organising and gap-finding tool. Used properly it tells you, far
faster than reading the file yourself, what you have, what disagrees, what is missing and
what to ask for next. It is a starting point for professional due diligence, not a
replacement for it.
