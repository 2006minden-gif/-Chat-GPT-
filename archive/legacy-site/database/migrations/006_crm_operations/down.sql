DROP TABLE IF EXISTS nd_crm_notifications;
DROP TABLE IF EXISTS nd_crm_conversions;
DROP TABLE IF EXISTS nd_crm_requests;
ALTER TABLE nd_employees DROP COLUMN position;
ALTER TABLE nd_orders DROP COLUMN due_on, DROP COLUMN notes;
ALTER TABLE nd_deals DROP COLUMN due_on, DROP COLUMN loss_reason;
