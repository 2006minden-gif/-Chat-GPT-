-- Immutable cost/pricing revisions. No actual rates, tax settings or financial seeds.
CREATE TABLE nd_cost_registry_keys (
 category VARCHAR(32) PRIMARY KEY,
 revision_number INT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cost_rates (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category VARCHAR(32) NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 value_scaled BIGINT UNSIGNED NOT NULL,
 currency CHAR(3) NOT NULL,
 source VARCHAR(500) NOT NULL,
 source_date DATE NOT NULL,
 valid_from DATE NOT NULL,
 valid_until DATE NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_rate_version(category,revision_number),
 KEY nd_rate_current(category,valid_from,valid_until,id),
 FOREIGN KEY (category) REFERENCES nd_cost_registry_keys(category) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_pricing_policies (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(190) NOT NULL,
 currency CHAR(3) NOT NULL,
 contingency_bp INT UNSIGNED NOT NULL,
 margin_bp INT UNSIGNED NOT NULL,
 minimum_bp INT UNSIGNED NOT NULL,
 overhead_bp INT UNSIGNED NOT NULL,
 effort_factor_bp INT UNSIGNED NOT NULL DEFAULT 10000,
 tax_bp INT UNSIGNED NULL,
 tax_method ENUM('unknown','none','included_percent') NOT NULL,
 source VARCHAR(500) NOT NULL,
 approved TINYINT UNSIGNED NOT NULL DEFAULT 0,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_project_estimates (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 artifact_id BIGINT UNSIGNED NULL,
 packages_json MEDIUMTEXT NOT NULL,
 scope_json TEXT NOT NULL,
 scope_hash CHAR(64) NOT NULL,
 provenance ENUM('ai','owner') NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_estimate_revision(project_id,revision_number),
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 FOREIGN KEY (artifact_id) REFERENCES nd_ai_artifacts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_quotations (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 estimate_id BIGINT UNSIGNED NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 policy_id BIGINT UNSIGNED NULL,
 calculation_json MEDIUMTEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 state ENUM('NEEDS_COST_REVIEW','DRAFT','APPROVED','REJECTED') NOT NULL,
 replaces_id BIGINT UNSIGNED NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_quote_revision(project_id,revision_number),
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 FOREIGN KEY (estimate_id) REFERENCES nd_project_estimates(id) ON DELETE RESTRICT,
 FOREIGN KEY (policy_id) REFERENCES nd_pricing_policies(id) ON DELETE RESTRICT,
 FOREIGN KEY (replaces_id) REFERENCES nd_quotations(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_pricing_decisions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 quotation_id BIGINT UNSIGNED NOT NULL UNIQUE,
 owner_id TINYINT UNSIGNED NOT NULL,
 decision ENUM('APPROVED','REJECTED') NOT NULL,
 quotation_hash CHAR(64) NOT NULL,
 reason VARCHAR(1000) NOT NULL,
 accepted_estimates TINYINT UNSIGNED NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (quotation_id) REFERENCES nd_quotations(id) ON DELETE RESTRICT,
 FOREIGN KEY (owner_id) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_project_actuals (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 quotation_id BIGINT UNSIGNED NOT NULL,
 owner_id TINYINT UNSIGNED NOT NULL,
 actual_cost_minor BIGINT UNSIGNED NOT NULL,
 development_milli INT UNSIGNED NOT NULL,
 testing_milli INT UNSIGNED NOT NULL,
 source VARCHAR(1000) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (quotation_id) REFERENCES nd_quotations(id) ON DELETE RESTRICT,
 FOREIGN KEY (owner_id) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_pricing_scan_state (
 id TINYINT UNSIGNED PRIMARY KEY,
 last_project BIGINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
