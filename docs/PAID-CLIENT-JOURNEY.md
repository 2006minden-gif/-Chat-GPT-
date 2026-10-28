# Invitation-only client journey — owner decision28October2026

Baseline production f09d10d, PR45, deployment40552424232. Read-only public
revalidation matches baseline assets and protected API401; public inquiry consent
privacy-2026-10-27-v2 approved; customer policy503 and login disabled. SMTP actual
readiness cannot be inferred from a disabled login/public response; its owner-only
status is available at /client-settings.php without returning credentials.

## Independent gates (first correction)

- Public inquiries: /#contact + /api.php?r=privacy, separate lead policy/consent.
  Customer auth, SMTP and registration are not prerequisites.
- Contract exchange before payment: baseline45 requires ca_enabled/account for
  sending and signed-copy upload. A separately scoped, expiring/revocable link
  workflow is a required next release; never open registration to work around it.
- Paid invitations: explicit owner action with customer and order IDs; approved
  customer privacy/consent, owner-opened portal, verified SpaceWeb mail/inbox code,
  owner-verified signed agreement and net actual manual bank attestation required.
  Customer 'I paid', zero-price schedules and local invoice/PDF do not qualify.
- Existing login: portal available, approved current customer privacy/consent,
  verified active account and password. Temporary outbound SMTP unavailability
  does not disable already verified login. Password recovery still needs mail.
- Public registration: always disabled by production overlay, independent of the
  portal setting. No owner settings switch enables it.

Invitations use existing hashed single-use customer tokens, expiry/reissue rules
and customer identities; no parallel account model. Activation rechecks actual
paid-customer eligibility. Full refund before activation blocks it. SMTP failure
revokes the new token; the owner can explicitly retry/reissue. API distinguishes
SMTP acceptance from inbox receipt. No mail credentials/token appear in reports
or Git; invitation secret is carried only in the email URL fragment. A successful
isolated SMTP receiver and link redemption prove the test journey; a202/queued/
mail_accepted event alone does not prove production inbox delivery.

Paper signing and owner review remain mandatory. Email token authenticates
account activation only; it is not a contractual signature. NPD receipt tasks
remain separate and manual in MyTax. Synthetic tests create no real payment and
no official tax receipt. Owner one-time production settings still require real
reviewed texts and actual mailbox verification via protected UI.

## Scoped paper documents (second correction)

018 is additive: hashed expiring/revocable links, hashed short-lived sessions,
quarantined private paper copies, and owner/prospect provenance events. It reuses
existing customer/order/document/template versions and validated private file
storage. No prospect account or false client/owner identity is created.

Owner explicitly enables document exchange only after approved purpose-scoped
privacy and preparation. Link creation requires selected exact proposal/agreement/
TZ binding IDs of one order and explicit owner confirmation. TLS or isolated
loopback test origin is required. Policy changes invalidate old grants. Each
session needs an unchecked separate consent before any document content.
Bearer secrets travel in a URL fragment, are removed from browser history, never
persist in plaintext in DB/request journals, and are displayed to the owner only
once for manual secure handover. Optional email uses only verified mail and the
customer's validated CRM email. Failed SMTP revokes the link. A duplicate create
request cannot regenerate/recover a bearer secret; it returns stable metadata and
requires explicit reissue, with request fingerprint conflicts rejected.

Guests can view only the exact rendered snapshots and submit PDF/JPG/PNG paper
copies for their scoped agreement/TZ. Shared validator, MIME/size/quota guards and
private storage are reused. Private quarantine metadata truthfully records the
prospect source. Owner downloads the private original and explicitly imports it
into the existing document file model; this import is not signature verification.
Only the separate owner verification action can set AGREED. Expiration/revocation
blocks future access; stored evidence remains available to its authorized owner.

No SMS/electronic signing provider is configured. Email tokens activate accounts
only and are never contractual signatures. NPD receipts remain manual MyTax
attachments; test payment attestations/unsigned synthetic paper fixtures occur
only in isolated test DBs, never as real production payment/receipt evidence.

Developer rehearsal covers the complete new journey with synthetic owner policy,
real loopback SMTP inbox reception and token redemption. It is not the requested
post-settings production acceptance: real owner-reviewed texts/requisites and
verified actual mailbox are still necessary. Do not mark completion on settings
flags, HTTP202, SMTP acceptance or queued/sent states alone.

Release/recovery:018 follows verified017 and uses the existing actual snapshot,
shadow-restore/hash/FK proof, exact SQL/operator pins and main-only deployment.
Automatic destructive/nonempty rollback remains forbidden; expired/revoked grants
and original paper copies remain evidence, not cleanup targets.
