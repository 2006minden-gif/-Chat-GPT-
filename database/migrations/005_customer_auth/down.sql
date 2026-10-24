-- Empty-only rollback is enforced by scripts/migrate-customer.php.
DROP TABLE IF EXISTS nd_customer_consents;
DROP TABLE IF EXISTS nd_customer_auth_events;
DROP TABLE IF EXISTS nd_customer_sessions;
DROP TABLE IF EXISTS nd_customer_tokens;
DROP TABLE IF EXISTS nd_customer_auth;
