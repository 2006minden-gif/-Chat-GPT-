-- Apply once after 002. Historical records remain NULL: no invented consent.
ALTER TABLE nd_leads
 ADD COLUMN consent TINYINT UNSIGNED NULL,
 ADD COLUMN consent_at BIGINT UNSIGNED NULL,
 ADD COLUMN policy_version VARCHAR(64) NULL,
 ADD COLUMN policy_hash CHAR(64) NULL;
