-- Durable invitation orchestration only; existing accounts, tokens and payments remain authoritative.
CREATE TABLE nd_lc_access_jobs (
 order_id BIGINT UNSIGNED PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 state ENUM('PENDING','BLOCKED','PROCESSING','SMTP_ACCEPTED','ACTIVATED','EXISTING_ACCOUNT','FAILED','UNCERTAIN','EXPIRED') NOT NULL DEFAULT 'PENDING',
 blocked_code VARCHAR(64) NULL,
 account_id BIGINT UNSIGNED NULL,
 triggering_transaction_id BIGINT UNSIGNED NULL,
 attempts INT UNSIGNED NOT NULL DEFAULT 0,
 next_attempt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lease_until DATETIME NULL,
 lease_token CHAR(64) NULL,
 issued_token_hash CHAR(64) NULL,
 smtp_accepted_at DATETIME NULL,
 activated_at DATETIME NULL,
 manual_reason TEXT NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 FOREIGN KEY (order_id) REFERENCES nd_orders(id) ON DELETE RESTRICT,
 FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT,
 FOREIGN KEY (triggering_transaction_id) REFERENCES nd_payment_transactions(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
