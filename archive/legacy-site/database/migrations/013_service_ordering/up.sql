-- Catalog and lifecycle bindings only. No service, price, rate or legal seeds.
CREATE TABLE nd_catalog_templates (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 title VARCHAR(190) NOT NULL,
 state VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
 head_revision INT UNSIGNED NOT NULL DEFAULT 1,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_template_versions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 template_id BIGINT UNSIGNED NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 body MEDIUMTEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 published_at DATETIME NULL,
 UNIQUE KEY nd_catalog_template_revision(template_id,revision_number),
 FOREIGN KEY (template_id) REFERENCES nd_catalog_templates(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_services (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 slug VARCHAR(80) NOT NULL UNIQUE,
 state VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
 head_revision INT UNSIGNED NOT NULL DEFAULT 1,
 published_revision INT UNSIGNED NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_service_versions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 service_id BIGINT UNSIGNED NOT NULL,
 template_version_id BIGINT UNSIGNED NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 body MEDIUMTEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 published_by TINYINT UNSIGNED NULL,
 published_at DATETIME NULL,
 UNIQUE KEY nd_catalog_service_revision(service_id,revision_number),
 FOREIGN KEY (service_id) REFERENCES nd_catalog_services(id) ON DELETE RESTRICT,
 FOREIGN KEY (template_version_id) REFERENCES nd_catalog_template_versions(id) ON DELETE RESTRICT,
 FOREIGN KEY (published_by) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_requests (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 account_id BIGINT UNSIGNED NOT NULL,
 service_version_id BIGINT UNSIGNED NOT NULL,
 package_key VARCHAR(32) NOT NULL,
 project_id BIGINT UNSIGNED NOT NULL UNIQUE,
 lead_id INT UNSIGNED NULL UNIQUE,
 deal_id BIGINT UNSIGNED NULL UNIQUE,
 order_id BIGINT UNSIGNED NULL UNIQUE,
 head_revision INT UNSIGNED NOT NULL DEFAULT 0,
 answers_json MEDIUMTEXT NOT NULL,
 file_ids_json TEXT NOT NULL,
 consent_at DATETIME NOT NULL,
 policy_version VARCHAR(64) NOT NULL,
 policy_hash CHAR(64) NOT NULL,
 state VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_catalog_customer(customer_id,id),
 FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT,
 FOREIGN KEY (service_version_id) REFERENCES nd_catalog_service_versions(id) ON DELETE RESTRICT,
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 FOREIGN KEY (lead_id) REFERENCES nd_leads(id) ON DELETE RESTRICT,
 FOREIGN KEY (deal_id) REFERENCES nd_deals(id) ON DELETE RESTRICT,
 FOREIGN KEY (order_id) REFERENCES nd_orders(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_briefs (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT UNSIGNED NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 answers_json MEDIUMTEXT NOT NULL,
 structured_json MEDIUMTEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 spec_revision_id BIGINT UNSIGNED NOT NULL,
 consent_at DATETIME NOT NULL,
 policy_version VARCHAR(64) NOT NULL,
 policy_hash CHAR(64) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_catalog_brief_revision(request_id,revision_number),
 FOREIGN KEY (request_id) REFERENCES nd_catalog_requests(id) ON DELETE RESTRICT,
 FOREIGN KEY (spec_revision_id) REFERENCES nd_cc_revisions(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_offers (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT UNSIGNED NOT NULL,
 brief_id BIGINT UNSIGNED NOT NULL,
 quotation_id BIGINT UNSIGNED NOT NULL,
 proposal_revision_id BIGINT UNSIGNED NOT NULL UNIQUE,
 body MEDIUMTEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 quotation_hash CHAR(64) NOT NULL,
 pricing_scope_hash CHAR(64) NOT NULL,
 state VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
 expires_at DATETIME NOT NULL,
 due_on DATE NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 published_by TINYINT UNSIGNED NULL,
 published_at DATETIME NULL,
 accepted_account_id BIGINT UNSIGNED NULL,
 accepted_at DATETIME NULL,
 accepted_checksum CHAR(64) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_catalog_offer_request(request_id,id),
 FOREIGN KEY (request_id) REFERENCES nd_catalog_requests(id) ON DELETE RESTRICT,
 FOREIGN KEY (brief_id) REFERENCES nd_catalog_briefs(id) ON DELETE RESTRICT,
 FOREIGN KEY (quotation_id) REFERENCES nd_quotations(id) ON DELETE RESTRICT,
 FOREIGN KEY (proposal_revision_id) REFERENCES nd_cc_revisions(id) ON DELETE RESTRICT,
 FOREIGN KEY (published_by) REFERENCES nd_admin(id) ON DELETE RESTRICT,
 FOREIGN KEY (accepted_account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_catalog_scope_transitions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 offer_id BIGINT UNSIGNED NOT NULL,
 stage VARCHAR(24) NOT NULL,
 from_hash CHAR(64) NOT NULL,
 to_hash CHAR(64) NOT NULL,
 scope_json MEDIUMTEXT NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_catalog_transition(offer_id,stage),
 FOREIGN KEY (offer_id) REFERENCES nd_catalog_offers(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
