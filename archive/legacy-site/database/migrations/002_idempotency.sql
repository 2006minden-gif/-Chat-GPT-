-- Apply once after 001. Nullable fields preserve historical records.
ALTER TABLE nd_leads
 ADD COLUMN request_key CHAR(64) NULL,
 ADD COLUMN request_hash CHAR(64) NULL,
 ADD UNIQUE INDEX nd_leads_request_key (request_key);
