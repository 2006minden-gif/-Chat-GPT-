# MAX notifications and public contact

Owner authorized MAX notifications, published bot @se14794003_bot, and supplied
her personal MAX profile URL for public contact. Personal MAX links on homepage
and service brief go to the owner, not to the notification bot. MAX brief uses
explicit manual copy/paste; no unsupported prefill query is invented.

API: official https://dev.max.ru/docs-api/methods/POST/messages and
https://dev.max.ru/docs-api/methods/POST/subscriptions, reviewed 27 October 2026.
Use platform-api2.max.ru, header Authorization, verified TLS, no redirects,
4-second transport timeout. No token in URLs/logs/Git/artifacts/browser storage.

The fixed-host MAX client also trusts the official Russian Trusted Root CA via
`private/notifications/russian-trusted-root.pem`; system CA directories remain
available. This changes no global trust store and keeps peer/name verification
enabled. Source: https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
(downloaded over verified HTTPS, 7 November 2026). DER SHA-256:
`d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31`.
MAX's current requirement: https://dev.max.ru/docs-api/ .

Read-only host diagnostics run when delivery fails or is deferred. They report
safe connection/identity/subscription metadata, never tokens, recipient IDs or
full webhook URLs. A persisted MAX delivery error makes the retry workflow fail
visibly; backoff and the durable queue continue to operate.
After a successfully published main release the same worker retries immediately,
so a repaired connection is not held by the old one-hour backoff. The owner's
manual retry also bypasses backoff without resetting acknowledged IDs.

Restoring outgoing site notifications does not require resetting the bot's
inbound webhook, token, recipient binding or acknowledgement ledger.

Authenticated owner settings (session+CSRF+same-origin) verify token via /me,
register an HTTPS webhook with a random secret, and return a 15-minute one-time
pair command. The owner sends it in a private bot chat; webhook checks the secret
header, private chat, sender and pair hash/expiry. The owner explicitly confirms
in CRM, which sends a real test message before enabling notifications. Merely
publishing code does not establish a live token or verified phone delivery.

State and secret live under private/notifications/runtime (directory0700,
files0600), outside explicit deployment file paths. Atomic replace and flock
serialize pairing/configuration/sending. Runtime files survive code deployments
and rollback. A disconnect invalidates pairing. No database migrations. Acknowledged IDs, rather than a MAX(id) cursor, prevent loss when insert commits arrive out of ID order.

Existing nd_leads is the durable queue; the private acknowledgement ledger advances only after
MAX acknowledges an actual message ID. Only new leads after connection are sent.
Notification payload contains just lead number and an authenticated CRM link,
not client name/contact/description. Failed sends preserve pending IDs and use
bounded exponential backoff. Immediate send is attempted after saving a lead;
therefore MAX failure never rejects or loses the saved lead. Idempotent form
replay also retries the queue without re-inserting a lead.

The main-only production SSH worker (same production concurrency lock as deploy)
retries up to10 messages using the existing deployment SSH secret bindings. The
GitHub schedule is nominally every5minutes and can be delayed; it is not an SLA.
No additional delivery pipeline, SSH grants, unverified hosts or TLS bypass.
MAX can accept a message before an acknowledgement/connection is lost, so a retry
can duplicate a notification in that ambiguous case; no exactly-once claim.

Privacy v2 adds the MAX contact route and minimal operator notification;
previous v1 text is preserved unchanged. Both current policy+consent remain
bound to recorded lead consent hash. CI uses disposable loopback DBs and injected
transport; it never contacts a real bot or persists real token. Production smoke
must not create fake client leads or read/send owner credentials.
