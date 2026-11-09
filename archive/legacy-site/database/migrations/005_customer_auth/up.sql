-- 005: customer authentication; additive, after journalled migration 004.
CREATE TABLE nd_customer_auth (
 account_id BIGINT UNSIGNED PRIMARY KEY,
 registration_method ENUM('self','invitation') NOT NULL,
 email_verified_at BIGINT UNSIGNED NULL,
 consent_at BIGINT UNSIGNED NOT NULL,
 policy_version VARCHAR(64) NOT NULL,
 policy_hash CHAR(64) NOT NULL,
 CONSTRAINT nd_auth_account_fk FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_customer_tokens (
 token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 account_id BIGINT UNSIGNED NOT NULL,
 purpose ENUM('verify','invite','reset') NOT NULL,
 created_at BIGINT UNSIGNED NOT NULL,
 expires_at BIGINT UNSIGNED NOT NULL,
 used_at BIGINT UNSIGNED NULL,
 issuer_admin_id TINYINT UNSIGNED NULL,
 KEY nd_ct_account_purpose (account_id,purpose,used_at),
 KEY nd_ct_expiry (expires_at),
 CONSTRAINT nd_ct_account_fk FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT,
 CONSTRAINT nd_ct_admin_fk FOREIGN KEY (issuer_admin_id) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_customer_sessions (
 token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 csrf_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 account_id BIGINT UNSIGNED NULL,
 created_at BIGINT UNSIGNED NOT NULL,
 expires_at BIGINT UNSIGNED NOT NULL,
 KEY nd_cs_account (account_id),
 KEY nd_cs_expiry (expires_at),
 CONSTRAINT nd_cs_account_fk FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_customer_auth_events (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 account_id BIGINT UNSIGNED NULL,
 actor_admin_id TINYINT UNSIGNED NULL,
 event VARCHAR(40) NOT NULL,
 created_at BIGINT UNSIGNED NOT NULL,
 KEY nd_ae_account_time (account_id,created_at),
 KEY nd_ae_time (created_at),
 CONSTRAINT nd_ae_account_fk FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT,
 CONSTRAINT nd_ae_admin_fk FOREIGN KEY (actor_admin_id) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_customer_consents (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 account_id BIGINT UNSIGNED NOT NULL,
 consent TINYINT UNSIGNED NOT NULL,
 consent_at BIGINT UNSIGNED NOT NULL,
 policy_version VARCHAR(64) NOT NULL,
 policy_hash CHAR(64) NOT NULL,
 purpose ENUM('registration','invitation','reconsent') NOT NULL,
 KEY nd_cc_account_time (account_id,consent_at),
 CONSTRAINT nd_cc_account_fk FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
