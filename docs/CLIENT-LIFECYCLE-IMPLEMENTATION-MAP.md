# Client-order lifecycle — implementation map, 27 October 2026

## Verified starting point

Production/main: `984ea3dfa5818817a40350836cccc346666699e8`, PR37,
Actions40475190178, evidence40475598393. Published application:34 explicit files,
owner account exists, legacy inquiry CRM, approved privacyv2 and configured MAX.
Production metadata: MySQL5.7.27, nd_admin/nd_leads/nd_sessions/nd_limits;
no004–013 migration journal. Do not infer deployment from a feature branch.
Ordinary connected-user PR → required checks → native protected integration →
SpaceWeb works. Missing unattended bot App credentials remain a separate issue;
no branch protection or held workflow run needs bypassing for these releases.

Reusable integrated candidate:
`origin/draft/integrated-release-package` at
`e07375f4cc564f7ce9d7c84211fb3fe0c42b2b79`. This is NOT production.
Preserve current public design, MAX runtime configuration, owner credentials,
consent records and existing files when extracting reviewed components.

| Requested capability | Existing source to reuse | Remaining work |
|---|---|---|
| Roles/invitations/self-registration | private/customer-auth.php, customer-mail.php; customer.php | deploy005, secure owner SMTP setup, invitation delivery evidence, scoped privacy approval |
| Customers/deals/orders/projects/tasks | private/crm/, workspace.php, portal.php;004–006 | safe live migration/recovery; hide historical employee UI in single-owner mode |
| Structured briefs/approved offers | private/catalog/;013 | preserve exact brief/spec/quote/package binding; owner lifecycle overview and next actions |
| Shared costs/estimates/price approval | private/pricing/, private/ai/;009–010 | preserve NEEDS_COST_REVIEW; manual drafting without paid provider; agreed payment schedules |
| Files/messages/document revisions/decisions | private/collab/;007 | reviewed template lifecycle, structured generation, signed-copy evidence, immutable agreement binding |
| Invoices/provider transactions | private/billing/;008 | add manual payment claims/bank verification, partial allocation/refunds; no live provider activation |
| Official NPD receipts | missing | separate owner issuance task/evidence for each verified payment; method-specific due dates; no fake fiscal output |
| Milestones/manual implementation/handover | private/production/, private/manual/;011–012 | actual deployment evidence, acceptance categories, agreement-based final settlement/handover gates |
| Cross-domain lifecycle/audit | existing scoped project/order history + request idempotency | explicit separate commercial/document/payment/delivery/acceptance states, transitions and overrides |
| Notifications | existing in-portal outbox; production MAX | use configured channels only, idempotent events/retries, honest delivery status |

## Release sequence

0. Repair the real data-delivery prerequisite: private DB snapshot plus actual
   isolated MySQL restore verification on the host, metadata-only evidence,
   exact reviewed additive migration plan, no restoration over client data.
A. Integrate reusable foundations and inquiry→brief→cost review→owner-approved
   proposal as a useful owner/client slice. Registration/invitations depend on
   explicit privacy/transport setup, not fabricated email verification.
B. Reviewed templates→private generated version→signed-copy agreement evidence.
C. Agreed payment schedule→client payment claim→owner bank verification→official
   NPD receipt task and authorized client access. No acquiring/banking access.
D. Materials/milestones→review→defect/revision/extra-scope decisions→acceptance.
E. Actual final settlement→handover→closure/support, then one marked synthetic
   end-to-end order, no real charges/fiscal documents or private-data exposure.

Each slice must pass real business/security tests, a legitimate PR, exact-main
production delivery and live verification. Gate only genuinely unavailable
features; never label the whole lifecycle complete after a partial release.
No duplicate customer/order/finance/cost registry models. New tables may extend
missing lifecycle/template/receipt semantics, referencing authoritative models.
Existing004–013 SQL/checksums remain immutable. Never auto-execute down or SQL
restore against production. Interrupted DDL must stop with exact evidence and a
reviewed forward recovery plan; existing runners do not safely resume partial
states automatically.

## Legal source checkpoints (reviewed before drafting)

- FNS NPD FAQ: https://npd.nalog.ru/faq/ — receipt timing differs for cash/electronic
  payment and other bank settlement; receipt tasks must not use one universal
  next-month deadline. Deposits are separate receipts, not counted again later.
- 422-FZ Art14 referenced by FNS; final implementation stores the applicable rule
  version, payment method, source and deadline, and encourages immediate issuance.
- Civil Code Arts160/434: written/electronic form requires the applicable content,
  identification and agreement basis. A checkbox/login is not automatically a
  legally sufficient signature. Default agreement evidence is uploaded signed
  copies plus recorded owner verification; electronic signing stays inactive.
- Owner-approved reviewed templates only. Drafts remain NEEDS_LEGAL_REVIEW until
  an explicit decision; no invented non-refundable deposits, silence acceptance,
  addresses, bank details, INN or signatory authority.

Current source references and owner-visible dependencies must be updated with
implementation evidence before calling a release DEPLOYED_AND_VERIFIED.

### Recovery prerequisite implementation

`scripts/deploy/recovery.php` snapshots actual InnoDB application rows in a
consistent read-only transaction into private base64/JSONL backup files. It
recreates schema/data in collision-checked random shadow tables in the same DB
(no CREATE DATABASE privilege or external data copy required), checks every row
hash and FK, and drops only the exact shadow tables it created. It rejects
unsupported tables/schema objects rather than claiming incomplete recovery.
Original tables are never restore targets. On failure code publication stops;
private backup/plan remain for diagnosis. Source values and secrets never enter
reports/artifacts. Five new real MySQL cases plus17 file/release recovery cases
passed locally on PHP8.4.27/MySQL5.7.44; production verification passed in PR38, main
`f7653f197e7c36b1de20cb46124816741997e92e`, deployment40481721385,
evidence40482158935. Actual4 tables/5 rows restored into private shadow tables;
original tables never written, shadow tables removed. Safe proof hashes:
backup `df6de08442b554f1a6179e88b2168ff3425a89a596ea3160caa835d2661246e3`,
schema `1dffaec5e35656f422f64ccc65828bb56caf1f7c302bdbf60c0d15f7e821c4d0`.

### Foundation slice A1 (release candidate)

Reuses exact004–013 SQL and existing customer/order/cost/document modules from
candidate e07375f. Exact SQL/operator pins are independently checked by the
builder and remote agent. Reviewed batch requires a previous healthy delivery,
previous and current real host data-recovery proofs, private dump and matching
migration journal. Only up, no down/restore. Partial DDL stops for reviewed
forward recovery. Loopback real MySQL5.7 test verifies complete batch and a
subsequent legitimate delivery, preserved owner row and all expanded FK checks.

Owner can qualify/link inquiries, manage customers/deals/draft orders/projects,
prepare scope, enter manual estimate packages, version Cost Registry and approve
an exact price. Production works in single-owner mode; employee routes,
assignments and controls disabled. Public design/MAX/owner account preserved.

This is A1 foundation, not completed slice A: client registration/invitations
remain inactive until scoped privacy and real SMTP configuration; customer
proposals/documents cannot be presented as agreed legal instruments. Order
confirmation/production transitions remain blocked pending real agreement and
payment schedule gates in subsequent slices. Paid AI/provider payments stay
inactive. No local PDF is an official receipt. All initial templates in the
next slice require explicit owner review and approval.


### Document slice B (release candidate)

014 adds versioned template/evidence metadata linked to existing orders, projects,
collaboration revisions and private files. No duplicate document contents or
customer/order model. Eight initial Russian templates are legal-review drafts;
only explicit owner approval of an exact checksum permits structured generation.
Required fields, INN control digits, bank-field format, actual approved quotation
and order total are checked on the server. Complete template/input/rendered-text
snapshots and SHA256 are immutable; ordinary collaboration editing cannot bypass
that rule. Private printable UTF8 output supports browser Save as PDF; no server
PDF library or fiscal document is claimed.

Client can see only sent own documents, provide comments and upload an existing
scoped private signed-copy file. Only owner verification of that actual file can
record agreement. Receipt of a click/comment/upload alone is not a signature.
Signed evidence cannot be hidden by ordinary file controls. Sending is unavailable
until client access/privacy configuration is actually enabled. Source checkpoints
and limitations are in LIFECYCLE-LEGAL-SOURCES.md.

Validation: 18 targeted real MySQL/HTTP/security/mobile/recovery tests pass,
including forbidden unapproved prices/templates, missing fields, client isolation,
XSS escaping, immutable document history, signed-copy roles, retry idempotency,
body tamper refusal, mobile375px, existing collaboration regression and actual
014 migration plus a subsequent expanded-schema recovery delivery.

### Payment slice C (release candidate)

015 extends existing invoices/attempts/transactions/refunds with immutable signed
schedule bindings, client claims, manual bank evidence and per-transaction NPD
receipt tasks. Two independent approvals are needed: actual signed agreement and
owner-approved invoice template. Agreed installments sum exactly to price;
deposits never become another final-balance income. Partial/overpayments are
visible. Client claim never creates income. Unique bank-operation hashes plus
request idempotency and order/invoice locks protect retries and concurrent edits.
Manual refunds record actual external bank operations; application initiates none.

Receipt tasks cover every verified installment, preserve payment method/FNS rule,
amount/date/buyer INN/service description and method-specific deadline. Real
MyTax issuance/correction/transmission evidence is owner-attested, explicitly not
independently verified. No fiscal receipt/QR is generated and no fake official
receipt is created in the tests. Refunds create correction-review tasks. Client
receipt access is independent from payment disputes. Protected evidence files
cannot be hidden by ordinary upload controls.

Validation: real MySQL payment/document/recovery tests pass; client claim vs
verification, partial payments, duplicate claims/bank IDs, deposit+balance sum,
overpayment/refund idempotency, receipt deadlines, forbidden local/foreign-host
fiscal evidence, role separation and invoice isolation. Mobile375px owner forms
and package closure pass. Live acquiring, bank and MyTax integrations remain off.


### Host delivery repair after PR39

PR39 integrated as09ad114, required checks passed. Main delivery40494989490
failed with generic private_subprocess_failed and verified file rollback; no
business release is claimed. Read-only preflight now exports only static safe
operator/dump error codes from prior private logs and current strict-mode flag,
never log text/config values. First cause must be confirmed from that evidence.

Reviewed batches already require and actually verify both prior/current host
JSONL+schema backups via shadow restore. That proven private backup is now the
canonical recovery artifact, removing a redundant dependency on a separately
configured mysqldump CLI. The legacy Stage3 additive contract still requires its
SQL dump. No backup/restore proof is bypassed, and restore remains manual only.

Migration operators establish STRICT_TRANS_TABLES for their own session if the
host default is non-strict, then verify it; global/server mode is untouched. SQL
004–013 bytes remain unchanged, and operator contents now have independent SHA256
pins as well as pinned SQL. Actual full-batch test passes against an isolated
MySQL5.7 host started with NO_ENGINE_SUBSTITUTION and proves its global mode is
unchanged.55 recovery/release/diagnostic checks pass in that environment.

CI executes every unique discovered test ID once. Only identical imported
TestCase IDs are deduplicated; distinct tests and import-failure cases remain.
The required Validate check, Apache/security/business/migration tests and
production gates remain in force.

### Retry integrity / non-strict runtime compatibility

The expanded order read model can exceed the legacy006 request journal TEXT
capacity. On non-strict MySQL this previously truncated the cached JSON, breaking
a later retry. New lifecycle mutations keep a small typed identity/version in the
existing journal and return/reload an explicitly current authorized projection;
replay never repeats the side effect. No duplicate journal/model or destructive
schema change. Corrupt historical cached results fail409 instead of re-executing.
Runtime connections now use UTC and a strict session, without changing global
host configuration. Ten targeted document/payment/runtime tests pass against
NO_ENGINE_SUBSTITUTION, including cached-document retries and corrupt-cache refusal.
