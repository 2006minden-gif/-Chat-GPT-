# Portfolio-only website

The owner requested retirement of the CRM, customer accounts, briefing/catalog pages and payment system on 9 November 2026.

The active application has only a homepage, portfolio with project detail views, and `/studio.php` for the owner's portfolio editor. Contacts go directly to the existing personal MAX and Telegram links. No lead form, customer login, AI assistant, payment initiation, analytics counter or CRM automation runs.

`public/site-router.php` is the exact route allowlist. Apache sends every non-asset request to it, including legacy PHP files still present on the host. Retired routes return HTTP 410. Private paths and source/backup copies are denied. `private/app.php` is a retirement guard, so old CLI jobs or entry points cannot bootstrap the old application. The notification worker and GitHub retry schedule are retired.

Existing administrator password hashes/sessions, portfolio records, revisions, media, unpublished drafts and historical publication grants are reused. Saving creates an immutable portfolio revision with optimistic concurrency protection. Uploads remain private until a work containing them is published. Removing a work archives it; original files and revisions are kept. Historical customer grants are not fabricated or modified. New publications require the owner's explicit rights confirmation, with permissions handled manually outside the retired CRM.

The old source, database definitions and obsolete business-flow tests are kept in `archive/legacy-site/` and are excluded from the release. Production tables and uploaded documents are not deleted, no schema migrations run, and verified full database backup/shadow-restore remains a mandatory deployment gate. The new focused suite verifies real mobile editing, authorization/CSRF, old route retirement (including actual Apache rewrites over leftover files), release integrity and recovery without source-row changes.

`manual-templates/NeuroDelo_shablony_DOCX.zip` contains six editable Word templates. Automation tokens are replaced by blank fields, and clauses depending on customer accounts/automatic access expiry are adapted to manual exchange. Original templates remain in the legacy archive.
