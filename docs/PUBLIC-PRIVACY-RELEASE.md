# Public privacy release — 26 October 2026

Owner explicitly supplied operator identity (Сухарева Наталья Владимировна,
самозанятая, Романово, Калининградская область), domain and Telegram contact,
and instructed that lead submission be enabled and the additions published.
This instruction supersedes the previous absence of owner approval for collection.
No email, street address, INN or legal review is invented.

The reviewed immutable public policy and separate consent are shipped in
private/legal/privacy-2026-10-26-v1.json. When no legacy policy version is configured,
its explicit activation_requested flag authorizes this release's form. Both texts
are bound into the policy hash recorded with consent on each lead. Missing,
malformed, incomplete or unapproved bundled documents disable submission.
Existing nonempty legacy policy versions keep their existing approval/file gate.
An explicit privacy_policy_disabled=true config flag overrides both paths.
Production config.php, privacy-policy.txt, credentials and existing data are never
rewritten. Deployment file backup and rollback cover the entire release.

The release adds ICO/SVG favicon, public map, XML sitemap, robots.txt and links
from public footers. It removes remote Google Fonts requests. The form retains
explicit unchecked consent, same-origin and server validation, rate limiting,
idempotency and existing database schema. No migration or synthetic live lead
is needed. CI exercises actual consent rejection, insertion and stored document
hash using a random loopback-only database. Production smoke must not insert
fake leads. GitHub App/TinyFish setup is independent of this publication.
