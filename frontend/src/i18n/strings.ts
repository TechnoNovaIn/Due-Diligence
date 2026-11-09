/** Interface strings in English and Kannada.
 *
 * Keys are stable identifiers; the Kannada column is what a Kannada-speaking
 * reviewer edits. Anything missing falls back to English rather than showing a
 * key, and `missingKannada()` reports the gap honestly.
 */
export type Lang = 'en' | 'kn'

export const LANGUAGES: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
]

type Entry = { en: string; kn?: string }

export const STRINGS: Record<string, Entry> = {
  // --- chrome ---
  'app.title': { en: 'Property Due Diligence', kn: 'ಸ್ವತ್ತು ಪರಿಶೀಲನಾ ವ್ಯವಸ್ಥೆ' },
  'nav.dashboard': { en: 'Dashboard', kn: 'ಮುಖಪುಟ' },
  'nav.cases': { en: 'Cases', kn: 'ಪ್ರಕರಣಗಳು' },
  'nav.newCase': { en: 'New case', kn: 'ಹೊಸ ಪ್ರಕರಣ' },
  'nav.system': { en: 'System', kn: 'ವ್ಯವಸ್ಥೆ' },
  'chrome.ai': { en: 'AI', kn: 'ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ' },
  'chrome.aiLocal': { en: 'local only', kn: 'ಸ್ಥಳೀಯ ಮಾತ್ರ' },
  'chrome.aiRemote': { en: 'remote', kn: 'ಹೊರಗಿನ ಸೇವೆ' },
  'chrome.ocr': { en: 'OCR', kn: 'ಪಠ್ಯ ಗುರುತಿಸುವಿಕೆ' },
  'chrome.ocrReady': { en: 'ready', kn: 'ಸಿದ್ಧ' },
  'chrome.ocrMissing': { en: 'not installed', kn: 'ಅಳವಡಿಸಿಲ್ಲ' },
  'chrome.watcher': { en: 'Watcher', kn: 'ಫೋಲ್ಡರ್ ನಿಗಾ' },
  'chrome.running': { en: 'running', kn: 'ಚಾಲನೆಯಲ್ಲಿದೆ' },
  'chrome.stopped': { en: 'stopped', kn: 'ನಿಂತಿದೆ' },
  'chrome.apiKey': { en: 'API key', kn: 'ಎಪಿಐ ಕೀ' },
  'chrome.language': { en: 'Language', kn: 'ಭಾಷೆ' },
  'chrome.disclaimer': {
    en: 'Preliminary automated assessment from the supplied documents. Not a title search, not an official verification, and not a legal opinion.',
    kn: 'ಸಲ್ಲಿಸಿದ ದಾಖಲೆಗಳ ಆಧಾರದ ಮೇಲೆ ಸ್ವಯಂಚಾಲಿತ ಪ್ರಾಥಮಿಕ ಮೌಲ್ಯಮಾಪನ. ಇದು ಹಕ್ಕು ತನಿಖೆಯಲ್ಲ, ಅಧಿಕೃತ ಪರಿಶೀಲನೆಯಲ್ಲ, ಕಾನೂನು ಅಭಿಪ್ರಾಯವೂ ಅಲ್ಲ.',
  },

  // --- severities (used by every badge) ---
  'severity.critical': { en: 'Critical', kn: 'ಅತಿ ಗಂಭೀರ' },
  'severity.high': { en: 'High', kn: 'ಗಂಭೀರ' },
  'severity.medium': { en: 'Medium', kn: 'ಮಧ್ಯಮ' },
  'severity.low': { en: 'Low', kn: 'ಕಡಿಮೆ' },
  'severity.informational': { en: 'Informational', kn: 'ಮಾಹಿತಿ' },

  // --- common ---
  'common.loading': { en: 'Loading…', kn: 'ಲೋಡ್ ಆಗುತ್ತಿದೆ…' },
  'common.retry': { en: 'Retry', kn: 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ' },
  'common.save': { en: 'Save', kn: 'ಉಳಿಸಿ' },
  'common.cancel': { en: 'Cancel', kn: 'ರದ್ದುಮಾಡಿ' },
  'common.clear': { en: 'Clear', kn: 'ತೆರವುಗೊಳಿಸಿ' },
  'common.delete': { en: 'Delete', kn: 'ಅಳಿಸಿ' },
  'common.none': { en: 'None', kn: 'ಯಾವುದೂ ಇಲ್ಲ' },
  'common.yes': { en: 'yes', kn: 'ಹೌದು' },
  'common.no': { en: 'no', kn: 'ಇಲ್ಲ' },
  'common.loadFailed': { en: 'Could not load.', kn: 'ಲೋಡ್ ಮಾಡಲಾಗಲಿಲ್ಲ.' },
  'common.why': { en: 'Why', kn: 'ಕಾರಣ' },
  'common.page': { en: 'page', kn: 'ಪುಟ' },
  'common.untranslated': { en: 'English', kn: 'ಇಂಗ್ಲಿಷ್' },
  'common.sourceScript': {
    en: 'Values and quotations are shown exactly as the documents write them, so a Kannada record reads in Kannada whichever language this interface is set to.',
    kn: 'ಮೌಲ್ಯಗಳು ಮತ್ತು ಉಲ್ಲೇಖಗಳನ್ನು ದಾಖಲೆಗಳಲ್ಲಿ ಇರುವಂತೆಯೇ ತೋರಿಸಲಾಗಿದೆ; ಆದ್ದರಿಂದ ಈ ತೆರೆಯ ಭಾಷೆ ಯಾವುದೇ ಆಗಿರಲಿ, ಇಂಗ್ಲಿಷ್ ದಾಖಲೆ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲೇ ಕಾಣಿಸುತ್ತದೆ.',
  },

  // --- dashboard ---
  'dash.title': { en: 'Dashboard', kn: 'ಮುಖಪುಟ' },
  'dash.newCase': { en: 'New property case', kn: 'ಹೊಸ ಸ್ವತ್ತು ಪ್ರಕರಣ' },
  'dash.totalCases': { en: 'Property cases', kn: 'ಸ್ವತ್ತು ಪ್ರಕರಣಗಳು' },
  'dash.underAnalysis': { en: 'Under analysis', kn: 'ವಿಶ್ಲೇಷಣೆಯಲ್ಲಿವೆ' },
  'dash.awaitingDocuments': { en: 'Awaiting documents', kn: 'ದಾಖಲೆಗಳಿಗೆ ಕಾಯುತ್ತಿವೆ' },
  'dash.criticalRisks': { en: 'Critical risks', kn: 'ಅತಿ ಗಂಭೀರ ಅಪಾಯಗಳು' },
  'dash.highFindings': { en: 'High findings', kn: 'ಗಂಭೀರ ಅಂಶಗಳು' },
  'dash.readyForReview': { en: 'Ready for review', kn: 'ಪರಿಶೀಲನೆಗೆ ಸಿದ್ಧ' },
  'dash.openRequirements': { en: 'Open requirements', kn: 'ಬಾಕಿ ಅಗತ್ಯಗಳು' },
  'dash.propertyCases': { en: 'Property cases', kn: 'ಸ್ವತ್ತು ಪ್ರಕರಣಗಳು' },
  'dash.noCases': { en: 'No cases yet', kn: 'ಇನ್ನೂ ಯಾವುದೇ ಪ್ರಕರಣವಿಲ್ಲ' },
  'dash.noCasesHint': {
    en: 'Create a case, then drop the property documents into its folder.',
    kn: 'ಪ್ರಕರಣವನ್ನು ಸೃಷ್ಟಿಸಿ, ನಂತರ ಸ್ವತ್ತಿನ ದಾಖಲೆಗಳನ್ನು ಅದರ ಫೋಲ್ಡರ್‌ಗೆ ಹಾಕಿ.',
  },
  'dash.recentDocuments': { en: 'Recently added documents', kn: 'ಇತ್ತೀಚೆಗೆ ಸೇರಿಸಿದ ದಾಖಲೆಗಳು' },
  'dash.recentReports': { en: 'Recent reports', kn: 'ಇತ್ತೀಚಿನ ವರದಿಗಳು' },
  'dash.pendingActions': { en: 'Pending mandatory actions', kn: 'ಬಾಕಿ ಇರುವ ಕಡ್ಡಾಯ ಕ್ರಮಗಳು' },
  'dash.nothingYet': { en: 'Nothing yet.', kn: 'ಇನ್ನೂ ಏನೂ ಇಲ್ಲ.' },
  'dash.noneOutstanding': { en: 'None outstanding.', kn: 'ಬಾಕಿ ಏನೂ ಇಲ್ಲ.' },

  // --- table headings ---
  'col.case': { en: 'Case', kn: 'ಪ್ರಕರಣ' },
  'col.property': { en: 'Property', kn: 'ಸ್ವತ್ತು' },
  'col.type': { en: 'Type', kn: 'ಪ್ರಕಾರ' },
  'col.docs': { en: 'Docs', kn: 'ದಾಖಲೆಗಳು' },
  'col.documents': { en: 'Documents', kn: 'ದಾಖಲೆಗಳು' },
  'col.openFindings': { en: 'Open findings', kn: 'ಬಾಕಿ ಅಂಶಗಳು' },
  'col.requirements': { en: 'Requirements', kn: 'ಅಗತ್ಯಗಳು' },
  'col.risk': { en: 'Risk', kn: 'ಅಪಾಯ' },
  'col.assessment': { en: 'Assessment', kn: 'ಮೌಲ್ಯಮಾಪನ' },
  'col.lastAnalysed': { en: 'Last analysed', kn: 'ಕೊನೆಯ ವಿಶ್ಲೇಷಣೆ' },
  'col.location': { en: 'Location', kn: 'ಸ್ಥಳ' },
  'col.findings': { en: 'Findings', kn: 'ಅಂಶಗಳು' },
  'col.reviewer': { en: 'Reviewer', kn: 'ಪರಿಶೀಲಕರು' },
  'col.updated': { en: 'Updated', kn: 'ನವೀಕರಿಸಲಾಗಿದೆ' },
  'col.file': { en: 'File', kn: 'ಕಡತ' },
  'col.documentDate': { en: 'Document date', kn: 'ದಾಖಲೆಯ ದಿನಾಂಕ' },
  'col.status': { en: 'Status', kn: 'ಸ್ಥಿತಿ' },
  'col.pages': { en: 'Pages', kn: 'ಪುಟಗಳು' },
  'col.extraction': { en: 'Extraction', kn: 'ಪಠ್ಯ ಓದುವಿಕೆ' },
  'col.received': { en: 'Received', kn: 'ಸ್ವೀಕರಿಸಿದ್ದು' },
  'col.issues': { en: 'Issues', kn: 'ಸಮಸ್ಯೆಗಳು' },
  'col.ref': { en: 'Ref', kn: 'ಸಂಕೇತ' },
  'col.severity': { en: 'Severity', kn: 'ತೀವ್ರತೆ' },
  'col.evidence': { en: 'Evidence', kn: 'ಸಾಕ್ಷ್ಯ' },
  'col.impact': { en: 'Potential impact', kn: 'ಸಂಭವನೀಯ ಪರಿಣಾಮ' },
  'col.action': { en: 'Recommended action', kn: 'ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ' },
  'col.version': { en: 'Version', kn: 'ಆವೃತ್ತಿ' },
  'col.generated': { en: 'Generated', kn: 'ಸಿದ್ಧಪಡಿಸಿದ್ದು' },
  'col.changed': { en: 'What changed', kn: 'ಏನು ಬದಲಾಯಿತು' },
  'col.export': { en: 'Export', kn: 'ರಫ್ತು' },
  'col.when': { en: 'When', kn: 'ಯಾವಾಗ' },
  'col.event': { en: 'Event', kn: 'ಘಟನೆ' },
  'col.actor': { en: 'Actor', kn: 'ನಿರ್ವಾಹಕರು' },
  'col.detail': { en: 'Detail', kn: 'ವಿವರ' },
  'col.versions': { en: 'Versions', kn: 'ಆವೃತ್ತಿಗಳು' },
  'col.field': { en: 'Field', kn: 'ವಿವರ' },
  'col.value': { en: 'Value', kn: 'ಮೌಲ್ಯ' },
  'col.source': { en: 'Source', kn: 'ಮೂಲ' },
  'col.consistent': { en: 'Consistent?', kn: 'ಹೊಂದಿಕೆಯೇ?' },
  'col.valuesAndSources': { en: 'Values and sources', kn: 'ಮೌಲ್ಯಗಳು ಮತ್ತು ಮೂಲಗಳು' },

  // --- case workspace ---
  'tab.overview': { en: 'Overview', kn: 'ಸಾರಾಂಶ' },
  'tab.documents': { en: 'Documents', kn: 'ದಾಖಲೆಗಳು' },
  'tab.analysis': { en: 'Document analysis', kn: 'ದಾಖಲೆ ವಿಶ್ಲೇಷಣೆ' },
  'tab.ownership': { en: 'Ownership timeline', kn: 'ಮಾಲೀಕತ್ವದ ಕಾಲಾನುಕ್ರಮ' },
  'tab.verification': { en: 'Cross-verification', kn: 'ಪರಸ್ಪರ ಪರಿಶೀಲನೆ' },
  'tab.risks': { en: 'Risk assessment', kn: 'ಅಪಾಯ ಮೌಲ್ಯಮಾಪನ' },
  'tab.missing': { en: 'Missing documents', kn: 'ಕೊರತೆಯ ದಾಖಲೆಗಳು' },
  'tab.actions': { en: 'Action items', kn: 'ಕೈಗೊಳ್ಳಬೇಕಾದ ಕ್ರಮಗಳು' },
  'tab.reports': { en: 'Reports', kn: 'ವರದಿಗಳು' },
  'tab.audit': { en: 'Audit history', kn: 'ಲೆಕ್ಕಪರಿಶೋಧನಾ ಇತಿಹಾಸ' },
  'case.scanFolder': { en: 'Scan folder now', kn: 'ಈಗ ಫೋಲ್ಡರ್ ಪರಿಶೀಲಿಸಿ' },
  'case.scanning': { en: 'Scanning…', kn: 'ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…' },
  'case.reanalyse': { en: 'Re-analyse', kn: 'ಮರು ವಿಶ್ಲೇಷಣೆ' },
  'case.analysing': { en: 'Analysing…', kn: 'ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ…' },
  'case.downloadPdf': { en: 'Download PDF', kn: 'ಪಿಡಿಎಫ್ ಡೌನ್‌ಲೋಡ್' },
  'case.deleteConfirm': {
    en: 'Delete this case? Documents on disk are not touched.',
    kn: 'ಈ ಪ್ರಕರಣವನ್ನು ಅಳಿಸಬೇಕೇ? ಡಿಸ್ಕ್‌ನಲ್ಲಿರುವ ದಾಖಲೆಗಳಿಗೆ ಏನೂ ಆಗುವುದಿಲ್ಲ.',
  },
  'case.jobsRunning': {
    en: 'background job(s) in progress — the report is held back until processing settles.',
    kn: 'ಹಿನ್ನೆಲೆ ಕೆಲಸಗಳು ನಡೆಯುತ್ತಿವೆ — ಪ್ರಕ್ರಿಯೆ ಮುಗಿಯುವವರೆಗೆ ವರದಿ ತಡೆಹಿಡಿಯಲಾಗುತ್ತದೆ.',
  },
  'case.notYetAssessed': { en: 'Not yet assessed', kn: 'ಇನ್ನೂ ಮೌಲ್ಯಮಾಪನ ಆಗಿಲ್ಲ' },
  'case.lastAnalysed': { en: 'last analysed', kn: 'ಕೊನೆಯ ವಿಶ್ಲೇಷಣೆ' },

  // --- overview ---
  'overview.analysed': { en: 'Analysed', kn: 'ವಿಶ್ಲೇಷಿಸಲಾಗಿದೆ' },
  'overview.pending': { en: 'Pending', kn: 'ಬಾಕಿ' },
  'overview.critical': { en: 'Critical', kn: 'ಅತಿ ಗಂಭೀರ' },
  'overview.caseDetails': { en: 'Case details', kn: 'ಪ್ರಕರಣದ ವಿವರಗಳು' },
  'overview.latestAssessment': { en: 'Latest assessment', kn: 'ಇತ್ತೀಚಿನ ಮೌಲ್ಯಮಾಪನ' },
  'overview.majorFindings': { en: 'Major findings', kn: 'ಪ್ರಮುಖ ಅಂಶಗಳು' },
  'overview.nextSteps': { en: 'Recommended next steps', kn: 'ಮುಂದಿನ ಶಿಫಾರಸು ಕ್ರಮಗಳು' },
  'overview.noReport': {
    en: 'No report yet. Add documents to the case folder, or use “Scan folder now”.',
    kn: 'ಇನ್ನೂ ವರದಿ ಇಲ್ಲ. ಪ್ರಕರಣದ ಫೋಲ್ಡರ್‌ಗೆ ದಾಖಲೆಗಳನ್ನು ಸೇರಿಸಿ, ಅಥವಾ "ಈಗ ಫೋಲ್ಡರ್ ಪರಿಶೀಲಿಸಿ" ಬಳಸಿ.',
  },
  'overview.overallRisk': { en: 'Overall risk', kn: 'ಒಟ್ಟಾರೆ ಅಪಾಯ' },
  'overview.score': { en: 'score', kn: 'ಅಂಕ' },
  'field.caseReference': { en: 'Case reference', kn: 'ಪ್ರಕರಣ ಸಂಕೇತ' },
  'field.address': { en: 'Address', kn: 'ವಿಳಾಸ' },
  'field.surveyNumber': { en: 'Survey number', kn: 'ಸರ್ವೇ ಸಂಖ್ಯೆ' },
  'field.location': { en: 'Location', kn: 'ಸ್ಥಳ' },
  'field.claimedOwner': { en: 'Claimed owner', kn: 'ಹೇಳಲಾದ ಮಾಲೀಕರು' },
  'field.seller': { en: 'Seller', kn: 'ಮಾರಾಟಗಾರರು' },
  'field.buyer': { en: 'Buyer', kn: 'ಖರೀದಿದಾರರು' },
  'field.reviewer': { en: 'Reviewer', kn: 'ಪರಿಶೀಲಕರು' },
  'field.jurisdiction': { en: 'Jurisdiction rules', kn: 'ವ್ಯಾಪ್ತಿಯ ನಿಯಮಗಳು' },
  'field.documentCollection': { en: 'Document collection', kn: 'ದಾಖಲೆ ಸಂಗ್ರಹ' },
  'field.watchFolder': { en: 'Watch folder', kn: 'ನಿಗಾ ಫೋಲ್ಡರ್' },
  'field.created': { en: 'Created', kn: 'ಸೃಷ್ಟಿಸಿದ್ದು' },

  // --- documents ---
  'docs.search': {
    en: "Search text inside this case's documents…",
    kn: 'ಈ ಪ್ರಕರಣದ ದಾಖಲೆಗಳಲ್ಲಿ ಪಠ್ಯ ಹುಡುಕಿ…',
  },
  'docs.anyStatus': { en: 'Any status', kn: 'ಯಾವುದೇ ಸ್ಥಿತಿ' },
  'docs.addFile': { en: 'Add file to folder', kn: 'ಫೋಲ್ಡರ್‌ಗೆ ಕಡತ ಸೇರಿಸಿ' },
  'docs.uploading': { en: 'Uploading…', kn: 'ಅಪ್‌ಲೋಡ್ ಆಗುತ್ತಿದೆ…' },
  'docs.none': { en: 'No documents yet', kn: 'ಇನ್ನೂ ದಾಖಲೆಗಳಿಲ್ಲ' },
  'docs.noneHint': {
    en: 'Copy the property documents into the case folder — they are picked up automatically.',
    kn: 'ಸ್ವತ್ತಿನ ದಾಖಲೆಗಳನ್ನು ಪ್ರಕರಣದ ಫೋಲ್ಡರ್‌ಗೆ ನಕಲಿಸಿ — ಅವು ತಾನಾಗಿಯೇ ಓದಲ್ಪಡುತ್ತವೆ.',
  },
  'docs.searchResults': { en: 'Search results for', kn: 'ಹುಡುಕಾಟದ ಫಲಿತಾಂಶ' },
  'docs.noMatch': { en: 'No match in this case.', kn: 'ಈ ಪ್ರಕರಣದಲ್ಲಿ ಏನೂ ಸಿಗಲಿಲ್ಲ.' },
  'docs.confidence': { en: 'confidence', kn: 'ವಿಶ್ವಾಸ' },

  // --- document viewer ---
  'viewer.backToCase': { en: 'Back to the case', kn: 'ಪ್ರಕರಣಕ್ಕೆ ಹಿಂತಿರುಗಿ' },
  'viewer.openOriginal': { en: 'Open original', kn: 'ಮೂಲ ದಾಖಲೆ ತೆರೆಯಿರಿ' },
  'viewer.reprocess': { en: 'Reprocess', kn: 'ಮರು ಪ್ರಕ್ರಿಯೆ' },
  'viewer.classification': { en: 'Classification', kn: 'ವರ್ಗೀಕರಣ' },
  'viewer.extractedInfo': { en: 'Extracted information', kn: 'ಹೊರತೆಗೆದ ಮಾಹಿತಿ' },
  'viewer.fields': { en: 'field(s)', kn: 'ವಿವರಗಳು' },
  'viewer.nothingExtracted': {
    en: 'Nothing was extracted from this document. Nothing has been assumed about its contents.',
    kn: 'ಈ ದಾಖಲೆಯಿಂದ ಏನೂ ಹೊರತೆಗೆಯಲಾಗಿಲ್ಲ. ಅದರ ವಿಷಯದ ಬಗ್ಗೆ ಏನನ್ನೂ ಊಹಿಸಲಾಗಿಲ್ಲ.',
  },
  'viewer.correct': { en: 'correct', kn: 'ತಿದ್ದಿ' },
  'viewer.originallyExtracted': { en: 'Originally extracted', kn: 'ಮೊದಲು ಓದಿದ್ದು' },
  'viewer.extractedText': { en: 'Extracted text — page', kn: 'ಹೊರತೆಗೆದ ಪಠ್ಯ — ಪುಟ' },
  'viewer.of': { en: 'of', kn: '/' },
  'viewer.previous': { en: 'Previous', kn: 'ಹಿಂದಿನ' },
  'viewer.next': { en: 'Next', kn: 'ಮುಂದಿನ' },
  'viewer.documentDate': { en: 'Document date', kn: 'ದಾಖಲೆಯ ದಿನಾಂಕ' },
  'viewer.pagesRead': { en: 'page(s) read', kn: 'ಪುಟಗಳನ್ನು ಓದಲಾಗಿದೆ' },
  'viewer.ocrUsed': { en: 'OCR used', kn: 'ಪಠ್ಯ ಗುರುತಿಸುವಿಕೆ ಬಳಸಲಾಗಿದೆ' },

  // --- ownership ---
  'ownership.note': {
    en: 'Each step reflects what a supplied document states. Nothing here has been verified against the Sub-Registrar’s record, and matching names across documents is not proof that the same person is involved.',
    kn: 'ಪ್ರತಿ ಹಂತವು ಸಲ್ಲಿಸಿದ ದಾಖಲೆ ಏನು ಹೇಳುತ್ತದೆ ಎಂಬುದನ್ನಷ್ಟೇ ತೋರಿಸುತ್ತದೆ. ಇದನ್ನು ಉಪ ನೋಂದಣಾಧಿಕಾರಿಗಳ ದಾಖಲೆಯೊಂದಿಗೆ ಪರಿಶೀಲಿಸಲಾಗಿಲ್ಲ; ದಾಖಲೆಗಳಲ್ಲಿ ಹೆಸರು ಹೊಂದಿಕೆಯಾಗುವುದು ಒಬ್ಬರೇ ವ್ಯಕ್ತಿ ಎಂಬುದಕ್ಕೆ ಪುರಾವೆಯಲ್ಲ.',
  },
  'ownership.none': { en: 'No ownership timeline yet', kn: 'ಇನ್ನೂ ಮಾಲೀಕತ್ವದ ಕಾಲಾನುಕ್ರಮವಿಲ್ಲ' },
  'ownership.noneHint': {
    en: 'A timeline is built from registered transfer documents (sale, gift, partition, settlement deeds and the like).',
    kn: 'ನೋಂದಾಯಿತ ವರ್ಗಾವಣೆ ದಾಖಲೆಗಳಿಂದ (ಕ್ರಯ, ದಾನ, ಪಾಲು, ಸಂಧಾನ ಪತ್ರ ಇತ್ಯಾದಿ) ಕಾಲಾನುಕ್ರಮ ರೂಪಿಸಲಾಗುತ್ತದೆ.',
  },
  'ownership.chain': { en: 'Chronological ownership chain', kn: 'ಕಾಲಾನುಕ್ರಮದ ಮಾಲೀಕತ್ವ ಸರಪಳಿ' },
  'ownership.gapBefore': { en: 'Gap before this transfer.', kn: 'ಈ ವರ್ಗಾವಣೆಗೂ ಮೊದಲು ಕೊರತೆ.' },
  'ownership.noDocument': { en: 'no document', kn: 'ದಾಖಲೆ ಇಲ್ಲ' },

  // --- cross verification ---
  'verify.comparison': {
    en: 'Field-by-field comparison across documents',
    kn: 'ದಾಖಲೆಗಳ ನಡುವೆ ವಿವರವಾರು ಹೋಲಿಕೆ',
  },
  'verify.consolidated': { en: 'Consolidated property record', kn: 'ಕ್ರೋಢೀಕೃತ ಸ್ವತ್ತು ದಾಖಲೆ' },
  'verify.consistent': { en: 'Consistent', kn: 'ಹೊಂದಿಕೆಯಾಗಿದೆ' },
  'verify.differs': { en: 'Differs', kn: 'ವ್ಯತ್ಯಾಸವಿದೆ' },
  'verify.notStated': { en: 'Not stated in any document.', kn: 'ಯಾವ ದಾಖಲೆಯಲ್ಲೂ ನಮೂದಿಸಿಲ್ಲ.' },
  'verify.none': { en: 'No cross-verification yet', kn: 'ಇನ್ನೂ ಪರಸ್ಪರ ಪರಿಶೀಲನೆ ಇಲ್ಲ' },

  // --- risks ---
  'risks.note': {
    en: 'The overall level is set by the most severe unresolved finding, never by an average, so one serious issue cannot be hidden by many minor ones. A finding marked “suspected” has not been confirmed by the evidence on record.',
    kn: 'ಒಟ್ಟಾರೆ ಮಟ್ಟವನ್ನು ಅತ್ಯಂತ ಗಂಭೀರವಾದ ಇತ್ಯರ್ಥವಾಗದ ಅಂಶವು ನಿರ್ಧರಿಸುತ್ತದೆ, ಸರಾಸರಿ ಅಲ್ಲ. ಹೀಗಾಗಿ ಅನೇಕ ಸಣ್ಣ ಅಂಶಗಳು ಒಂದು ಗಂಭೀರ ಸಮಸ್ಯೆಯನ್ನು ಮರೆಮಾಡಲಾರವು. "ಶಂಕಿತ" ಎಂದು ಗುರುತಿಸಿದ ಅಂಶವನ್ನು ದಾಖಲೆಗಳು ದೃಢಪಡಿಸಿಲ್ಲ.',
  },
  'risks.anySeverity': { en: 'Any severity', kn: 'ಯಾವುದೇ ತೀವ್ರತೆ' },
  'risks.anyStatus': { en: 'Any status', kn: 'ಯಾವುದೇ ಸ್ಥಿತಿ' },
  'risks.noMatch': { en: 'No findings match', kn: 'ಹೊಂದುವ ಅಂಶಗಳಿಲ್ಲ' },
  'risks.noMatchHint': {
    en: 'Change the filters, or add more documents.',
    kn: 'ಶೋಧಕಗಳನ್ನು ಬದಲಿಸಿ, ಅಥವಾ ಹೆಚ್ಚಿನ ದಾಖಲೆಗಳನ್ನು ಸೇರಿಸಿ.',
  },
  'risks.confirmed': { en: 'confirmed', kn: 'ದೃಢಪಟ್ಟಿದೆ' },
  'risks.suspected': { en: 'suspected', kn: 'ಶಂಕಿತ' },
  'risks.documentsRequired': { en: 'Documents required', kn: 'ಅಗತ್ಯವಿರುವ ದಾಖಲೆಗಳು' },
  'risks.verification': { en: 'Verification', kn: 'ಪರಿಶೀಲನೆ' },
  'risks.requiresLegalReview': {
    en: 'requires professional legal review',
    kn: 'ವೃತ್ತಿಪರ ಕಾನೂನು ಪರಿಶೀಲನೆ ಅಗತ್ಯ',
  },
  'risks.firstReported': { en: 'first reported in version', kn: 'ಮೊದಲು ವರದಿಯಾದ ಆವೃತ್ತಿ' },
  'risks.resolution': { en: 'Resolution', kn: 'ಇತ್ಯರ್ಥ' },
  'risks.statusPrompt': {
    en: 'Why is this finding being changed? This is recorded in the audit history.',
    kn: 'ಈ ಅಂಶವನ್ನು ಏಕೆ ಬದಲಾಯಿಸಲಾಗುತ್ತಿದೆ? ಇದು ಲೆಕ್ಕಪರಿಶೋಧನಾ ಇತಿಹಾಸದಲ್ಲಿ ದಾಖಲಾಗುತ್ತದೆ.',
  },

  // --- missing documents ---
  'missing.note': {
    en: 'A requirement listed here is something still to be obtained or done. The absence of a document is not itself proof of a defect — it means the point has not been verified. Requirement sets are jurisdiction templates and have not been confirmed by local counsel.',
    kn: 'ಇಲ್ಲಿ ಪಟ್ಟಿ ಮಾಡಿದ ಅಗತ್ಯವೆಂದರೆ ಇನ್ನೂ ಪಡೆಯಬೇಕಾದ ಅಥವಾ ಮಾಡಬೇಕಾದ ಕೆಲಸ. ದಾಖಲೆ ಇಲ್ಲದಿರುವುದು ದೋಷಕ್ಕೆ ಪುರಾವೆಯಲ್ಲ — ಆ ಅಂಶವನ್ನು ಪರಿಶೀಲಿಸಲಾಗಿಲ್ಲ ಎಂದಷ್ಟೇ ಅರ್ಥ. ಈ ಅಗತ್ಯಗಳ ಪಟ್ಟಿಯನ್ನು ಸ್ಥಳೀಯ ವಕೀಲರು ದೃಢಪಡಿಸಿಲ್ಲ.',
  },
  'missing.showClosed': {
    en: 'Show requirements already met, waived or withdrawn',
    kn: 'ಈಗಾಗಲೇ ಪೂರೈಸಿದ, ಕೈಬಿಟ್ಟ ಅಥವಾ ಹಿಂಪಡೆದ ಅಗತ್ಯಗಳನ್ನು ತೋರಿಸಿ',
  },
  'missing.none': { en: 'No requirements recorded yet', kn: 'ಇನ್ನೂ ಯಾವುದೇ ಅಗತ್ಯ ದಾಖಲಾಗಿಲ್ಲ' },
  'missing.whyRequired': { en: 'Why required', kn: 'ಏಕೆ ಅಗತ್ಯ' },
  'missing.resolves': { en: 'Resolves', kn: 'ಪರಿಹರಿಸುತ್ತದೆ' },
  'missing.period': { en: 'Period / relates to', kn: 'ಅವಧಿ / ಸಂಬಂಧ' },
  'missing.whereToObtain': { en: 'Where to obtain it', kn: 'ಎಲ್ಲಿ ಪಡೆಯಬೇಕು' },
  'missing.nextAction': { en: 'Next action', kn: 'ಮುಂದಿನ ಕ್ರಮ' },
  'missing.riskIfAbsent': { en: 'Risk of proceeding without it', kn: 'ಇಲ್ಲದೆ ಮುಂದುವರಿಯುವ ಅಪಾಯ' },
  'missing.closesWhen': { en: 'Closes when', kn: 'ಯಾವಾಗ ಮುಗಿಯುತ್ತದೆ' },
  'missing.note_': { en: 'Note', kn: 'ಟಿಪ್ಪಣಿ' },
  'missing.jurisdictionNotConfirmed': {
    en: 'jurisdiction not confirmed',
    kn: 'ವ್ಯಾಪ್ತಿ ದೃಢಪಟ್ಟಿಲ್ಲ',
  },
  'missing.notePrompt': {
    en: 'Note (recorded in the audit history):',
    kn: 'ಟಿಪ್ಪಣಿ (ಲೆಕ್ಕಪರಿಶೋಧನಾ ಇತಿಹಾಸದಲ್ಲಿ ದಾಖಲಾಗುತ್ತದೆ):',
  },
  'missing.group.statutory': {
    en: '1. Potentially required by applicable law',
    kn: '೧. ಅನ್ವಯವಾಗುವ ಕಾನೂನಿನ ಪ್ರಕಾರ ಅಗತ್ಯವಿರಬಹುದು',
  },
  'missing.group.conditional': {
    en: '2. Conditionally required for this property',
    kn: '೨. ಈ ಸ್ವತ್ತಿಗೆ ಷರತ್ತುಬದ್ಧವಾಗಿ ಅಗತ್ಯ',
  },
  'missing.group.discrepancy': {
    en: '3. Needed to resolve identified discrepancies',
    kn: '೩. ಕಂಡುಬಂದ ವ್ಯತ್ಯಾಸಗಳನ್ನು ಪರಿಹರಿಸಲು ಅಗತ್ಯ',
  },
  'missing.group.recommended': {
    en: '4. Recommended for stronger due diligence',
    kn: '೪. ಹೆಚ್ಚು ಸದೃಢ ಪರಿಶೀಲನೆಗೆ ಶಿಫಾರಸು',
  },
  'missing.group.external_check': {
    en: '5. External verification not yet performed',
    kn: '೫. ಇನ್ನೂ ನಡೆಸದ ಹೊರಗಿನ ಪರಿಶೀಲನೆಗಳು',
  },
  'missing.group.professional': {
    en: '6. Professional assessments still pending',
    kn: '೬. ಬಾಕಿ ಇರುವ ವೃತ್ತಿಪರ ಮೌಲ್ಯಮಾಪನಗಳು',
  },

  // --- actions ---
  'actions.plan': { en: 'Recommended action plan', kn: 'ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ ಯೋಜನೆ' },
  'actions.questions': {
    en: 'Questions for the seller or property owner',
    kn: 'ಮಾರಾಟಗಾರರಿಗೆ ಅಥವಾ ಸ್ವತ್ತಿನ ಮಾಲೀಕರಿಗೆ ಪ್ರಶ್ನೆಗಳು',
  },
  'actions.noQuestions': {
    en: 'No outstanding question arises from the current evidence.',
    kn: 'ಪ್ರಸ್ತುತ ದಾಖಲೆಗಳಿಂದ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಉದ್ಭವಿಸುವುದಿಲ್ಲ.',
  },
  'actions.dependsOn': { en: 'Depends on', kn: 'ಇದನ್ನು ಅವಲಂಬಿಸಿದೆ' },
  'actions.none': { en: 'No action plan yet', kn: 'ಇನ್ನೂ ಕ್ರಮ ಯೋಜನೆ ಇಲ್ಲ' },

  // --- reports ---
  'reports.generate': { en: 'Generate a new version', kn: 'ಹೊಸ ಆವೃತ್ತಿ ಸಿದ್ಧಪಡಿಸಿ' },
  'reports.generating': { en: 'Generating…', kn: 'ಸಿದ್ಧಪಡಿಸಲಾಗುತ್ತಿದೆ…' },
  'reports.openFull': { en: 'Open full report', kn: 'ಪೂರ್ಣ ವರದಿ ತೆರೆಯಿರಿ' },
  'reports.latestVersion': { en: 'Latest version', kn: 'ಇತ್ತೀಚಿನ ಆವೃತ್ತಿ' },
  'reports.version': { en: 'Version', kn: 'ಆವೃತ್ತಿ' },
  'reports.history': { en: 'Version history', kn: 'ಆವೃತ್ತಿಗಳ ಇತಿಹಾಸ' },
  'reports.preview': { en: 'Report preview', kn: 'ವರದಿಯ ಮುನ್ನೋಟ' },
  'reports.none': { en: 'No report versions yet', kn: 'ಇನ್ನೂ ವರದಿಯ ಆವೃತ್ತಿಗಳಿಲ್ಲ' },
  'reports.noneHint': {
    en: 'A version is produced automatically once the documents in the folder have been processed.',
    kn: 'ಫೋಲ್ಡರ್‌ನಲ್ಲಿರುವ ದಾಖಲೆಗಳನ್ನು ಓದಿದ ನಂತರ ಆವೃತ್ತಿ ತಾನಾಗಿಯೇ ಸಿದ್ಧವಾಗುತ್ತದೆ.',
  },

  // --- audit ---
  'audit.filter': {
    en: 'Filter by event type or message…',
    kn: 'ಘಟನೆಯ ಪ್ರಕಾರ ಅಥವಾ ಸಂದೇಶದಿಂದ ಶೋಧಿಸಿ…',
  },
  'audit.none': { en: 'No audit events', kn: 'ಯಾವುದೇ ಘಟನೆಗಳಿಲ್ಲ' },

  // --- new case form ---
  'new.title': { en: 'New property case', kn: 'ಹೊಸ ಸ್ವತ್ತು ಪ್ರಕರಣ' },
  'new.intro': {
    en: 'A dedicated folder is created for this case. Drop every document relating to the property into it — the system picks up new, replaced and removed files on its own.',
    kn: 'ಈ ಪ್ರಕರಣಕ್ಕೆ ಪ್ರತ್ಯೇಕ ಫೋಲ್ಡರ್ ಸೃಷ್ಟಿಯಾಗುತ್ತದೆ. ಸ್ವತ್ತಿಗೆ ಸಂಬಂಧಿಸಿದ ಪ್ರತಿ ದಾಖಲೆಯನ್ನೂ ಅದರಲ್ಲಿ ಹಾಕಿ — ಹೊಸ, ಬದಲಾದ ಮತ್ತು ತೆಗೆದ ಕಡತಗಳನ್ನು ವ್ಯವಸ್ಥೆ ತಾನಾಗಿಯೇ ಗುರುತಿಸುತ್ತದೆ.',
  },
  'new.property': { en: 'Property', kn: 'ಸ್ವತ್ತು' },
  'new.identifiers': { en: 'Identifiers and location', kn: 'ಗುರುತುಗಳು ಮತ್ತು ಸ್ಥಳ' },
  'new.parties': { en: 'Parties and scope', kn: 'ಪಕ್ಷಗಾರರು ಮತ್ತು ವ್ಯಾಪ್ತಿ' },
  'new.propertyName': { en: 'Property name or reference', kn: 'ಸ್ವತ್ತಿನ ಹೆಸರು ಅಥವಾ ಸಂಕೇತ' },
  'new.propertyType': { en: 'Property type', kn: 'ಸ್ವತ್ತಿನ ಪ್ರಕಾರ' },
  'new.transactionType': { en: 'Transaction type', kn: 'ವ್ಯವಹಾರದ ಪ್ರಕಾರ' },
  'new.purpose': { en: 'Purpose of this due diligence', kn: 'ಈ ಪರಿಶೀಲನೆಯ ಉದ್ದೇಶ' },
  'new.watchFolder': {
    en: 'Watch folder (optional — one is created if left blank)',
    kn: 'ನಿಗಾ ಫೋಲ್ಡರ್ (ಐಚ್ಛಿಕ — ಖಾಲಿ ಬಿಟ್ಟರೆ ಹೊಸದು ಸೃಷ್ಟಿಯಾಗುತ್ತದೆ)',
  },
  'new.create': { en: 'Create case', kn: 'ಪ್ರಕರಣ ಸೃಷ್ಟಿಸಿ' },
  'new.creating': { en: 'Creating…', kn: 'ಸೃಷ್ಟಿಯಾಗುತ್ತಿದೆ…' },
  'new.extent': { en: 'Extent', kn: 'ವಿಸ್ತೀರ್ಣ' },
  'new.unit': { en: 'Unit', kn: 'ಅಳತೆ ಘಟಕ' },
  'new.subdivision': { en: 'Subdivision / hissa', kn: 'ಹಿಸ್ಸಾ' },
  'new.khataNumber': { en: 'Khata number', kn: 'ಖಾತಾ ಸಂಖ್ಯೆ' },
  'new.plotNumber': { en: 'Plot number', kn: 'ನಿವೇಶನ ಸಂಖ್ಯೆ' },
  'new.flatNumber': { en: 'Flat / unit number', kn: 'ಫ್ಲಾಟ್ ಸಂಖ್ಯೆ' },
  'new.village': { en: 'Village', kn: 'ಗ್ರಾಮ' },
  'new.taluk': { en: 'Taluk', kn: 'ತಾಲ್ಲೂಕು' },
  'new.district': { en: 'District', kn: 'ಜಿಲ್ಲೆ' },
  'new.state': { en: 'State', kn: 'ರಾಜ್ಯ' },

  // --- cases list ---
  'cases.search': {
    en: 'Search property, owner, survey number…',
    kn: 'ಸ್ವತ್ತು, ಮಾಲೀಕರು, ಸರ್ವೇ ಸಂಖ್ಯೆ ಹುಡುಕಿ…',
  },
  'cases.anyRisk': { en: 'Any risk level', kn: 'ಯಾವುದೇ ಅಪಾಯ ಮಟ್ಟ' },
  'cases.anyType': { en: 'Any property type', kn: 'ಯಾವುದೇ ಸ್ವತ್ತಿನ ಪ್ರಕಾರ' },
  'cases.noMatch': { en: 'No matching cases', kn: 'ಹೊಂದುವ ಪ್ರಕರಣಗಳಿಲ್ಲ' },
  'cases.noMatchHint': {
    en: 'Adjust the filters, or create a new case.',
    kn: 'ಶೋಧಕಗಳನ್ನು ಬದಲಿಸಿ, ಅಥವಾ ಹೊಸ ಪ್ರಕರಣ ಸೃಷ್ಟಿಸಿ.',
  },

  // --- system page ---
  'system.title': { en: 'System', kn: 'ವ್ಯವಸ್ಥೆ' },
  'system.whatLeaves': { en: 'What leaves this machine:', kn: 'ಈ ಗಣಕದಿಂದ ಹೊರಹೋಗುವುದು:' },
  'system.aiProcessing': { en: 'AI processing', kn: 'ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ ಪ್ರಕ್ರಿಯೆ' },
  'system.textExtraction': { en: 'Text extraction and OCR', kn: 'ಪಠ್ಯ ಓದುವಿಕೆ ಮತ್ತು ಗುರುತಿಸುವಿಕೆ' },
  'system.folderMonitoring': { en: 'Folder monitoring', kn: 'ಫೋಲ್ಡರ್ ನಿಗಾ' },
  'system.backgroundJobs': { en: 'Background jobs', kn: 'ಹಿನ್ನೆಲೆ ಕೆಲಸಗಳು' },
  'system.storage': { en: 'Storage', kn: 'ಸಂಗ್ರಹಣೆ' },
  'system.security': { en: 'Security', kn: 'ಭದ್ರತೆ' },
  'system.languages': { en: 'Languages', kn: 'ಭಾಷೆಗಳು' },
  'system.noLimit': { en: 'No limit', kn: 'ಮಿತಿ ಇಲ್ಲ' },
  'system.ocrLanguages': { en: 'OCR languages', kn: 'OCR ಭಾಷೆಗಳು' },
  'system.cannotRead': { en: 'cannot read', kn: 'ಓದಲಾಗುವುದಿಲ್ಲ' },
  'system.maxFileSize': { en: 'Max file size', kn: 'ಗರಿಷ್ಠ ಕಡತದ ಗಾತ್ರ' },
  'system.maxPages': { en: 'Max pages per document', kn: 'ದಾಖಲೆಗೆ ಗರಿಷ್ಠ ಪುಟಗಳು' },
}

export function translate(key: string, lang: Lang): string {
  const entry = STRINGS[key]
  if (!entry) return key
  if (lang === 'kn' && entry.kn) return entry.kn
  return entry.en
}

/** Keys with no Kannada text yet — surfaced on the System page rather than hidden. */
export function missingKannada(): string[] {
  return Object.entries(STRINGS).filter(([, v]) => !v.kn).map(([k]) => k)
}
