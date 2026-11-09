# Portfolio-only website

The active application contains a homepage, portfolio and project views, and `/studio.php` for the owner's portfolio editor. Contacts link directly to personal MAX and Telegram. There is no CRM, lead capture, customer login, briefing, payments, notification automation or AI assistant.

Public routes are explicitly allowed in `public/site-router.php`. Unknown routes return 404. Apache also routes leftover physical legacy PHP files through this allowlist while the removal is in progress.

Portfolio storage is independent: `nd_pf_items`, `nd_pf_versions`, `nd_pf_media`. Authentication reuses `nd_admin`, `nd_sessions`, `nd_limits`, preserving the owner's password and sessions. No active query joins orders, customer permissions or contract tables. Version JSON, checksums, IDs, slugs and media files are preserved. Historical visibility is imported from existing owner rights or matching signed grants without inventing grants. New publication requires the owner's rights confirmation.

The one-time deployment transition freezes writes, copies all old application files/documents/configuration to a nonpublic 0700 archive, renames legacy tables into the `nd_archive_*` namespace in one atomic operation, and verifies full backup/shadow restoration before importing portfolio data. The new editor remains read-only during publication checks. Once the new application is verified, all legacy files are moved out of working directories into the closed archive. Configuration is reduced to database connection and site URL. Known obsolete cron jobs are removed while preserving unrelated entries. Legacy source is removed from the default repository; historical commits retain it.

Archive: `.neurodelo-retired/<release-id>/`, outside the public root, with 0600 private files. It preserves original documents, source/configuration and a verified complete database snapshot. Historical database rows remain only in archived tables. They are not read by the site. This preserves records rather than destroying customer data.

Before physical cleanup, a failed release restores the old table names and previous code while writes are frozen. Cleanup failures retain the verified independent site and report pending removal; they never silently roll back to the old CRM. Interrupted cleanup is resumable.

Tests cover mobile create/upload/publish/edit/archive, authorization/CSRF, Apache routing, reversible table transition, exact row/checksum preservation, private documents/configuration preservation, schema drift and corrupt archive rejection. Six manual Word templates remain in `manual-templates/`.
