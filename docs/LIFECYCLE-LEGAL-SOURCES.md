# Legal-source checkpoint — 27 October 2026

Before writing initial Russian review drafts, checked:

- FNS official NPD FAQ https://npd.nalog.ru/faq/ (accessed27.10.2026): owner-issued MyTax receipts, payment-method-specific timing. This implementation does not issue fiscal receipts or validate the owner's current NPD registration.
- Civil Code160/434 current consolidated text (including22.10.2026 changes shown by source): https://www.consultant.ru/document/cons_doc_LAW_5142/95f9ba225766dcfec8461f257ed0b179d032c5b7/ and https://www.consultant.ru/document/cons_doc_LAW_5142/08b8673b58e230c76f61b3a81736d4b2fd9ea3d2/ . Identification and applicable agreement matter; no ordinary login/checkbox is claimed as an electronic signature. Default evidence is an uploaded signed copy with an explicit recorded owner verification.
- Rospotrebnadzor official publication https://zpp.rospotrebnadzor.ru/npa/federal/192115 (publication is an older consolidation) and current consolidated Art32 https://www.consultant.ru/document/cons_doc_LAW_305/758e2cfdf136a621c8f66dcb3372b772c7b5e6e8/ . Applicable mandatory consumer rights must not be replaced by invented non-refundable deposits or silence acceptance. Consumer applicability and mixed development/IP/service terms require deliberate owner review.

Initial eight templates are NEEDS_LEGAL_REVIEW, never approved automatically.
Configurable sections require explicit structured owner input. No INN, bank,
full address, authority, transfer of rights, refund term or support period is
invented. Owner may approve a reviewed version directly; external lawyer
approval is not an imposed prerequisite. The application records that decision,
not a representation that a government or lawyer approved the text.

Templates allow only a fixed list of text placeholders, never PHP/HTML/AI
execution. Generated snapshots bind exact owner-approved template, validated
fields, project/order and approved quotation. Old drafts are not legal agreements.
Client data collection and registration remain gated by purpose-scoped approved
privacy and real mail transport; publishing this code alone does not enable them.

## Payment/receipt implementation checkpoint

FNS FAQ rechecked before implementation: payment/receipt timing sections and
Art14 references, plus correction/refund explanation under Art8(4). Each actual
owner-verified transaction, including each deposit/partial payment, creates one
receipt task with a unique transaction FK. Cash/electronic methods use the actual
payment instant; other bank settlement uses9th of the following month,23:59:59
Europe/Kaliningrad, stored in UTC. Immediate issuance is encouraged for all.
Issuance and transmission have distinct owner-recorded timestamps/evidence.
A signed act, invoice or local PDF is never labelled an independently verified
FNS receipt. Official-link host is restricted to lknpd.nalog.ru; files require
owner confirmation of actual MyTax issuance. The application never creates a
fiscal number/QR, annuls a receipt, transfers money or connects a bank. Refund
recording creates an explicit MyTax review/correction task and preserves history.

## Client activation checkpoint (27October2026)

Current Article9 requires consent separately from other documents:
https://mintrud.gov.ru/docs/laws/130 and
https://www.consultant.ru/document/Cons_doc_LAW_61801/6c94959bc017ac80140621762d2ac59f6006b08c/ .
The customer consent is a separate versioned page; no prechecked box, contract
acceptance, payment verification or advertising consent is bundled with it.
Operator-specific legal basis, retention and processors require real owner review.

SpaceWeb's SMTP configuration source:
https://help.sweb.ru/nastrojka-smtp-na-sajte_973.html .
Fixed smtp.spaceweb.ru465SSL uses the actual mailbox login/from and protected
password input, with peer verification. A real received-code challenge follows
SMTP acceptance; no fake mailbox or transport credential is seeded in production.

## Separate supplied DOCX package checkpoint — 28 October 2026

Rechecked official FNS NPD FAQ (https://npd.nalog.ru/faq/), Mintrud 152-FZ
publication (https://mintrud.gov.ru/docs/laws/130), and official Rospotrebnadzor
consumer-law publication (https://zpp.rospotrebnadzor.ru/npa/federal/192115).
These official publications do not establish an independent legal review or
current suitability of every supplied clause. No substantive legal clauses
were drafted or rewritten by this import. The six owner-supplied standalone
DOCX files replace the combined package as new source templates; each starts
NEEDS_LEGAL_REVIEW and requires exact owner approval. Internal guide and source
notes stay outside customer PDFs. Paper-copy review is an owner attestation,
not an automatic signature check. MyTax receipts remain manual. Publication
permissions do not automatically authorize identifying-data or photo publication.
