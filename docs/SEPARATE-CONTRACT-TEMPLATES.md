# Separate contractual documents — source and operating record

This release continues PR48 / production579d3b7; it does not replace CRM/auth,
SpaceWeb SMTP, private uploads, bank attestation, MyTax or the deployment pipeline.

The exact manifest allowlist imports six owner-supplied DOCX files individually
into nd_lc_templates as NEEDS_LEGAL_REVIEW. Migration019 seeds missing exact
source hashes idempotently, never infers approval, and preserves previous versions.
The combined Word package is superseded for new production contractual output.
Legacy issued/signed documents remain immutable and accessible. Legacy proposals,
payment requests, handover and support models remain in use for their own purposes.
Internal guide and manifest are stored in docs only and never rendered. Original
editable DOCX sources are outside public_html, accessible only through owner auth.

## Owner paths

- /contract-settings.php: versioned incomplete draft/reviewed owner details;
  order-scoped customer version review; explicit approved terms tied to an exact
  sent owner-approved proposal/quotation; standalone PDF generation.
- /documents.php?mode=owner#templates: six source templates, exact review/approval,
  owner-only editable DOCX download and conspicuously fictional PDF samples.
- /prospect-owner.php: explicit details permission with zero document IDs, or an
  exact list of document IDs; expiry/revocation; optional verified SMTP delivery.
- /documents.php?mode=owner#document/ID: download/inspect actual immutable PDF,
  acknowledge its hash before send, separately review uploaded paper originals,
  record and release an owner-uploaded countersigned copy, release payment schedule.
- /orders.php?mode=owner: bind the real reviewed paper agreement to the sent
  proposal; /finance.php?mode=owner: existing actual-bank attestation and MyTax tasks.
- /client-settings.php: actual owner privacy/method decisions and real inbox code.

Customer links use /prospect.php#token=SECRET. Token is removed from history,
hashed at rest, exchanged for HttpOnly scoped session, never included in PDF URLs.
Explicit current policy consent precedes data exchange. Details-only links cannot
read any document; a document scope cannot write details unless explicitly granted.
Order IDs alone never authorize downloads. Authorized activated clients get the
same binding/PDF through /documents.php and lifecycle-api.php, with no reentry of
reviewed contract data. No public registration is enabled.

PDFs are rendered offline in PHP8.4 with vendored tFPDF1.34 and embedded DejaVu
regular/bold fonts. No external service, executable or browser printing required.
Sources/metrics are immutable, no writable PHP font caches. License notices and
LGPL2.1/font terms accompany the private distribution. Each PDF has one selected
source, the supplied brand logo once per page,13pt text, approx1.4 line spacing,
black text, generous paragraph spacing, and page n/total footer. Private storage
uses existing shared quota/locking,0600 files and SHA256 verification on download.

Required values, exact template approval, current reviewed party profiles, proposal
price, payment totals/dates and rights remuneration block unresolved final output.
Optional absent postal/review fields are removed cleanly; no home address invented.
Milestone JSON expands fully with result/date/criteria/amount and exact total.
Existing accepted-final/change evidence gates apply to those document types.
Publication permission requests are optional at completion and do not activate
publication or substitute for any separately required data/image legal basis.

Uploads preserve each original PDF/photo. No conversion or automated signature
verification occurs. Import, owner signature review, completed-copy release and
payment release are distinct audited steps. Guest payment claims are messages,
not bank transactions or account activation. Invitations now require complete
owner-verified payment of the first agreed installment, not any positive amount.
Email edits in customer details never silently update CRM delivery addresses.
SMTP acceptance is recorded separately from actual receipt/activation evidence.

019 is four additive tables; existing schema/data/settings/uploads are preserved.
Exact SQL/operator hashes are pinned in the existing reviewed deployment allowlist.
The full existing recovery/shadow-restore rehearsal remains mandatory. No automatic
DB rollback; CLI down refuses nonempty new tables. Code rollback preserves records.
No completed/customer documents, credentials or real test-bank records go to Git.

## Verification and limits

Isolated HTTP+MySQL rehearsal covers inquiry→details→review→separate PDFs→private
paper upload/import/review→owner completed copy→payment instructions→synthetic
manual bank→actual loopback mailbox message→single-use activation→own-order/PDF
access. Also incorrect recipient, missing consent/CSRF, expired/revoked scopes,
expired/reused invitation, duplicate bank event, incomplete qualifying payment,
SMTP failure, version conflicts, draft templates, missing fields, private originals,
immutable history and migration/recovery. Mobile browser saves/reloads owner draft
and exercises dynamic customer types. Poppler extracts text/font metadata and
rasterizes all pages of all six standalone PDFs. None is a real payment/FNS receipt.

Publishing code does not attest to actual owner legal review, real bank details or
production inbox delivery. Final real-settings acceptance remains separate until
the owner completes the protected policy/requisites/template gates and actual
controlled test-message receipt is observed. Never label a queued/sent flag as
successful delivery or create fictitious actual bank records in production.

Production defaults require the new package for newly generated agreement/TZ/act/
change/publication-permission documents. This does not retire or rewrite a sent
or signed historical version. No postal address is universally required for a
proposal or the new package; if the owner has a transaction-specific need it must
be reviewed explicitly. Customer optional fields irrelevant to the selected type
are cleared server-side to avoid needless retention.
