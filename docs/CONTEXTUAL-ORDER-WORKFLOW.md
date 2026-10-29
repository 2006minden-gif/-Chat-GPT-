# Contextual owner workflow — release 1

Continues production d0f8437/PR49; no replacement CRM, authentication, document
engine, catalog, bank integration or legal decisions.

/order-workflow.php is the owner entry point: readiness and exact pending/active
policy versions; inquiry selection; atomic link to existing CRM entities; readable
order context and next-action links through qualification, estimate/proposal,
customer details, private PDFs/paper review, finance, invitation and acceptance.
A new inquiry creates only a draft order with an explicitly unapproved price.
Retry or a second browser action cannot create another customer/order/project for
the same inquiry. A stale inquiry version cannot overwrite current data.

020 adds one relation between an existing lead, order and project. It does not
store another copy of customer details. Exact additive SQL/operator pins and the
existing shadow-restore recovery pipeline remain mandatory. Nonempty rollback is
refused. MAX-only source contacts use truthful MAX notes on the existing customer,
not invented email/phone values or a Telegram field.

owner-context.js adds readable selectors to existing forms. Original controls and
operations remain authoritative; IDs travel internally and original numeric types
are preserved. It carries the order across internal navigation, scopes files,
documents, quotations, stages and revisions, and prefills existing reviewed data.
No approval/confirmation checkbox is selected automatically. Applying a price is
an explicit owner action requiring an existing fresh approved quote and an editable
draft order; server versions and idempotency remain enforced.

Public service descriptions/brief tool now explain the local-only result and
separate inquiry submission. Messenger links are preserved. The owner receives a
read-only proposed mapping from the four existing public directions to the ONE
existing managed catalog. No service, questionnaire or commercial price is
published or approved by the mapping. A messenger-only inquiry is recorded in CRM
by the owner; no fabricated public consent is inserted on the customer's behalf.

Owner readiness and CLI-only deployment diagnostics separate public inquiry,
scoped document exchange, paid invitations and existing-client login. The CLI
returns only gate booleans, exact legal versions/hashes and template metadata;
no email credentials, mail settings object, contract content or customer data.
Publishing never approves policy, templates or profiles. Existing mailbox
verification is retained; a new probe is not requested automatically.

This first release does NOT claim automatic payment-to-invitation delivery or
production journey acceptance. These remain the next independent release/test.
Owner decisions about commercial terms, legal templates, actual paper copies,
actual bank receipt, MyTax and handover remain manual.
