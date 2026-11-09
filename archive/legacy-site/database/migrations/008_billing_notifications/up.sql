-- Additive only. Monetary values are RUB minor units, UTC timestamps.
CREATE TABLE nd_billing_sequences (
 year SMALLINT UNSIGNED PRIMARY KEY,
 last_number BIGINT UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_invoices (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 order_id BIGINT UNSIGNED NOT NULL,
 number VARCHAR(64) NULL UNIQUE,
 state ENUM('draft','issued','cancelled') NOT NULL DEFAULT 'draft',
 currency CHAR(3) NOT NULL DEFAULT 'RUB',
 total_minor BIGINT UNSIGNED NOT NULL,
 due_on DATE NOT NULL,
 snapshot MEDIUMTEXT NULL,
 snapshot_hash CHAR(64) NULL,
 replaces_id BIGINT UNSIGNED NULL,
 sent_at DATETIME NULL,
 issued_at DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 KEY nd_invoice_customer(customer_id,state,id),
 KEY nd_invoice_order(order_id,id),
 KEY nd_invoice_due(state,due_on,id),
 FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 FOREIGN KEY (customer_id,order_id) REFERENCES nd_orders(customer_id,id) ON DELETE RESTRICT,
 FOREIGN KEY (replaces_id) REFERENCES nd_invoices(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_invoice_lines (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 invoice_id BIGINT UNSIGNED NOT NULL,
 position SMALLINT UNSIGNED NOT NULL,
 description VARCHAR(500) NOT NULL,
 quantity_milli INT UNSIGNED NOT NULL,
 unit_minor BIGINT UNSIGNED NOT NULL,
 total_minor BIGINT UNSIGNED NOT NULL,
 UNIQUE KEY nd_invoice_position(invoice_id,position),
 FOREIGN KEY (invoice_id) REFERENCES nd_invoices(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_payment_attempts (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 invoice_id BIGINT UNSIGNED NOT NULL,
 request_key CHAR(64) NOT NULL UNIQUE,
 provider VARCHAR(32) NOT NULL,
 merchant_hash CHAR(64) NOT NULL,
 provider_id VARCHAR(128) NULL UNIQUE,
 amount_minor BIGINT UNSIGNED NOT NULL,
 currency CHAR(3) NOT NULL,
 state ENUM('creating','pending','succeeded','canceled') NOT NULL DEFAULT 'creating',
 redirect_url TEXT NULL,
 last_error VARCHAR(32) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 verified_at DATETIME NULL,
 next_check DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_attempt_invoice(invoice_id,state,id),
 KEY nd_attempt_check(state,next_check,id),
 FOREIGN KEY (invoice_id) REFERENCES nd_invoices(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_payment_transactions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 attempt_id BIGINT UNSIGNED NOT NULL UNIQUE,
 provider_id VARCHAR(128) NOT NULL UNIQUE,
 amount_minor BIGINT UNSIGNED NOT NULL,
 currency CHAR(3) NOT NULL,
 settled_at DATETIME NOT NULL,
 FOREIGN KEY (attempt_id) REFERENCES nd_payment_attempts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_payment_events (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 event_key CHAR(64) NOT NULL UNIQUE,
 attempt_id BIGINT UNSIGNED NOT NULL,
 state VARCHAR(32) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (attempt_id) REFERENCES nd_payment_attempts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_refunds (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 attempt_id BIGINT UNSIGNED NOT NULL,
 request_key CHAR(64) NOT NULL UNIQUE,
 provider_id VARCHAR(128) NULL UNIQUE,
 amount_minor BIGINT UNSIGNED NOT NULL,
 reason VARCHAR(500) NOT NULL,
 state ENUM('creating','pending','succeeded','canceled') NOT NULL DEFAULT 'creating',
 last_error VARCHAR(32) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 verified_at DATETIME NULL,
 next_check DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_refund_attempt(attempt_id,state,id),
 KEY nd_refund_check(state,next_check,id),
 FOREIGN KEY (attempt_id) REFERENCES nd_payment_attempts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_invoice_adjustments (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 invoice_id BIGINT UNSIGNED NOT NULL,
 amount_minor BIGINT UNSIGNED NOT NULL,
 reason VARCHAR(500) NOT NULL,
 request_key CHAR(64) NOT NULL UNIQUE,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (invoice_id) REFERENCES nd_invoices(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_notification_outbox (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 event_key VARCHAR(160) NOT NULL,
 recipient_type ENUM('owner','customer') NOT NULL,
 recipient_id BIGINT UNSIGNED NOT NULL,
 channel ENUM('in_app','email') NOT NULL,
 template VARCHAR(64) NOT NULL,
 template_version SMALLINT UNSIGNED NOT NULL DEFAULT 1,
 entity VARCHAR(32) NOT NULL,
 record_id BIGINT UNSIGNED NOT NULL,
 title VARCHAR(190) NOT NULL,
 essential TINYINT UNSIGNED NOT NULL DEFAULT 1,
 state ENUM('pending','processing','delivered','failed','disabled','skipped') NOT NULL DEFAULT 'pending',
 attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
 next_attempt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lease_until DATETIME NULL,
 lease_token CHAR(64) NULL,
 last_error VARCHAR(32) NULL,
 read_at DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 delivered_at DATETIME NULL,
 UNIQUE KEY nd_outbox_event(event_key,recipient_type,recipient_id,channel),
 KEY nd_outbox_due(state,next_attempt,id),
 KEY nd_outbox_recipient(recipient_type,recipient_id,channel,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_notification_preferences (
 account_id BIGINT UNSIGNED PRIMARY KEY,
 optional_email TINYINT UNSIGNED NOT NULL DEFAULT 0,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
