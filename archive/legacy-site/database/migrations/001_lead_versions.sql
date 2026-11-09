-- Apply once to an existing installation after backup. Fresh schema already includes it.
ALTER TABLE nd_leads ADD COLUMN version INT UNSIGNED NOT NULL DEFAULT 1;
