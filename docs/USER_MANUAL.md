# User manual

## Choosing a language

The **English / ಕನ್ನಡ** control in the header switches the whole system. The choice is
remembered in this browser and is also sent to the server, so the case list, the findings,
the checklist and the report all come back in that language. Reports can be exported in
either language independently of the interface setting.

Kannada documents are read whichever language the interface is in — the two settings are
independent. [LANGUAGES.md](LANGUAGES.md) sets out what is translated and what is not.

## Creating a case

**New case** asks for the property name and type, and optionally the identifiers you
already know (survey number, khata, village, taluk, district), the parties and the purpose.
None of it is required beyond the name and type — but anything you supply is cross-checked
against the documents, so a typo in the survey number will be reported as a discrepancy.

The system creates a folder and shows you its path. You can instead point the case at a
folder you already have by filling in **Watch folder**; it must sit under a configured
`ALLOWED_WATCH_ROOTS` path, otherwise it is refused.

**Property type matters.** The checklist adapts to it: an apartment asks for the UDS,
approved plan, OC and RERA registration; agricultural land asks for the RTC, mutation
records and survey sketch; a residential plot carved out of agricultural land asks for the
conversion order and the approved layout.

## Adding documents

Copy files into the case folder. Sub-folders are fine. Supported: PDF, DOCX, DOC, RTF,
TXT, JPG, JPEG, PNG, TIFF, BMP, WEBP.

**There is no size or page limit.** A 2,000-page deed book is read in full, and a
250 MB file is handled without difficulty. If you ever want a cap — on a shared machine,
say — set `MAX_FILE_MB` or `MAX_PAGES_PER_DOCUMENT`; a document that hits one is reported
as truncated rather than silently cut short.

The watcher waits until a file has stopped changing before reading it, so a slow copy or a
download in progress is never processed half-written. A full sweep also runs every two
minutes, which picks up anything added while the system was stopped.

You can also use **Add file to folder** in the Documents tab — it writes into the same
folder and takes the same path through the pipeline.

**Replacing a document:** save the new file over the old one. The previous version is kept
and marked superseded; the new one is read and the assessment updated.

**Removing a document:** delete the file. The record is marked removed, the findings that
depended on it are re-evaluated, and nothing is erased from the history.

## Reading the case

| Tab | What it is for |
|---|---|
| **Overview** | The current assessment, why it was reached, the major findings and the next steps. |
| **Documents** | Every file with its type, dates, status, page count, extraction confidence and issues. Full-text search across the case is here. |
| **Document analysis** | Per-document narrative: purpose, parties, dates, identifiers, legal effect, what it references but does not contain, and what needs verifying. |
| **Ownership timeline** | The chain reconstructed from the deeds, with gaps marked. Partitions and settlements appear as *allocations* — they divide a joint holding, and which schedule went to whom has to be confirmed from the document. |
| **Cross-verification** | Field-by-field comparison across documents, and the consolidated property record with each value marked documented, corroborated, conflicting or missing. |
| **Risk assessment** | The register. Filter by severity and status; open a finding to see its evidence, follow the citation to the page, and set its status. |
| **Missing documents** | The checklist in six groups, each item with why it is required, where to obtain it, the risk of going without, and what closes it. |
| **Action items** | The prioritised plan and the questions to put to the seller. |
| **Reports** | Every version with its change log, an inline preview and PDF/HTML export. |
| **Audit history** | Every event, with the ruleset and model version in force at the time. |

## Correcting what the system read

Open a document from the Documents tab. Each extracted field shows its value, the page it
came from and the sentence that supports it.

- **correct** replaces a value. The original is kept, the field is marked
  `user_corrected`, and the correction survives reprocessing.
- The **document type** dropdown overrides the automatic classification — use it when a
  document comes back as *Unknown*. Confidence becomes 1.0 and the case is re-analysed.
- **Reprocess** re-reads the file, for instance after installing OCR or supplying a better
  scan.

Both actions are recorded in the audit history with your username.

## Working through findings

A finding is **confirmed** when the evidence on record establishes it, and **suspected**
when the documents only point at it. Set the status as you work:

- **Resolved** — the underlying issue has been dealt with. Record how.
- **Accepted** — the risk is known and accepted. It still contributes to the score, at a
  quarter weight, and stays in the report.
- **Not applicable** — the finding does not apply to this property.

If the next analysis re-detects a finding you closed, it reopens with a note, because the
evidence still supports it.

## Closing a requirement

Collect the document, put it in the folder, and let the system close the requirement when
it has read it and the related finding resolves. If you verified something outside the
system — a phone call to the bank, an EC you checked at the Sub-Registrar's office — set
the status by hand and write a note. From that point the engine leaves it alone.

## Reports

A new version is produced whenever documents or findings change materially. Versions are
never overwritten. The change log tells you exactly what moved: findings added, status
changes, documents added or removed, requirements opened and closed, and any change to the
overall assessment.

Export the PDF from the case header or the Reports tab.

## Reading the assessment honestly

The overall level is the **worst unresolved finding**, never an average, so one serious
issue cannot be diluted by a long list of minor ones. The numerical score is shown
alongside as a secondary indicator only.

The five possible statuses:

| Status | Meaning |
|---|---|
| Assessment Incomplete | Documents are still processing, or a mandatory requirement is unmet. |
| High-Risk Findings Identified | At least one critical or high finding is unresolved. |
| Further Verification Required | Medium findings or discrepancy-driven requirements remain open. |
| No Material Issues Identified in Reviewed Evidence | Nothing above low severity in what was reviewed — stated together with the scope. |
| Ready for Independent Professional Review | The evidence is organised and the outstanding points documented for a professional. |

The system will not tell you a property is safe to buy. It tells you what the documents
show, what they disagree about, and what has not been checked.

## When something does not work

- **A document shows "Needs manual review".** Either it could not be read (a scan with no
  OCR engine available, or a page too poor to recognise), or its type could not be
  determined. Supply a clearer copy, check the **System** page to see whether an OCR engine
  is live, or set the type by hand.
- **A scanned Kannada document was not read.** macOS Vision cannot read Kannada. Install
  Tesseract with the Kannada pack and set `OCR_LANGUAGE=eng+kan` — see
  [LANGUAGES.md](LANGUAGES.md). Kannada PDFs that already have a text layer (Bhoomi, Kaveri)
  need none of this.
- **Some text stays in English with an "English" tag.** A finding's detailed description
  quotes the documents directly and is generated in English. It is marked rather than
  mistranslated; the title, the consequence and the recommended action are in Kannada.
- **A file was ignored.** Hidden files, `README.txt` in the case folder, temporary files
  (`~$…`, `.part`, `.crdownload`) and unsupported extensions are skipped by design. A file
  whose contents do not match its extension is quarantined.
- **Nothing is being picked up.** Check the System page: the watcher should say *running*.
  **Scan folder now** forces an immediate sweep.
- **The report seems stale.** Report generation waits until no document is still in flight.
  The case header shows how many background jobs are outstanding.
