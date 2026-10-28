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
