-- Private collaboration. Additive; explicit CLI migration only.
CREATE TABLE nd_cc_messages (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 actor_type ENUM('owner','customer') NOT NULL,
 actor_id BIGINT UNSIGNED NOT NULL,
 body TEXT NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_cc_message_project (project_id,id),
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_reads (
 project_id BIGINT UNSIGNED NOT NULL,
 actor_type ENUM('owner','customer') NOT NULL,
 actor_id BIGINT UNSIGNED NOT NULL,
 last_message_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
 PRIMARY KEY (project_id,actor_type,actor_id),
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_files (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 storage_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 display_name VARCHAR(190) NOT NULL,
 mime VARCHAR(100) NOT NULL,
 size_bytes INT UNSIGNED NOT NULL,
 checksum CHAR(64) NOT NULL,
 actor_type ENUM('owner','customer') NOT NULL,
 actor_id BIGINT UNSIGNED NOT NULL,
 visibility ENUM('internal','customer') NOT NULL DEFAULT 'internal',
 archived_at DATETIME NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_cc_file_project (project_id,visibility,id),
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_message_files (
 message_id BIGINT UNSIGNED NOT NULL,
 file_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY (message_id,file_id),
 FOREIGN KEY (message_id) REFERENCES nd_cc_messages(id) ON DELETE RESTRICT,
 FOREIGN KEY (file_id) REFERENCES nd_cc_files(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_documents (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 stage_id BIGINT UNSIGNED NULL,
 kind ENUM('specification','description','plan','deliverable','final','milestone') NOT NULL,
 title VARCHAR(190) NOT NULL,
 head_revision INT UNSIGNED NOT NULL DEFAULT 1,
 archived_at DATETIME NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_cc_document_project (project_id,kind,id),
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 FOREIGN KEY (project_id,stage_id) REFERENCES nd_project_stages(project_id,id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_revisions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 document_id BIGINT UNSIGNED NOT NULL,
 revision_number INT UNSIGNED NOT NULL,
 body MEDIUMTEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 status ENUM('draft','ready','sent','approved','changes_requested','finalized') NOT NULL DEFAULT 'draft',
 version INT UNSIGNED NOT NULL DEFAULT 1,
 archived_at DATETIME NULL,
 sent_at DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_cc_revision_number (document_id,revision_number),
 FOREIGN KEY (document_id) REFERENCES nd_cc_documents(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_revision_files (
 revision_id BIGINT UNSIGNED NOT NULL,
 file_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY (revision_id,file_id),
 FOREIGN KEY (revision_id) REFERENCES nd_cc_revisions(id) ON DELETE RESTRICT,
 FOREIGN KEY (file_id) REFERENCES nd_cc_files(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_approvals (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 revision_id BIGINT UNSIGNED NOT NULL UNIQUE,
 checksum CHAR(64) NOT NULL,
 target_version INT UNSIGNED NULL,
 status ENUM('pending','approved','changes_requested','withdrawn') NOT NULL DEFAULT 'pending',
 due_on DATE NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (revision_id) REFERENCES nd_cc_revisions(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_cc_decisions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 approval_id BIGINT UNSIGNED NOT NULL UNIQUE,
 account_id BIGINT UNSIGNED NOT NULL,
 decision ENUM('approved','changes_requested') NOT NULL,
 feedback TEXT NOT NULL,
 checksum CHAR(64) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (approval_id) REFERENCES nd_cc_approvals(id) ON DELETE RESTRICT,
 FOREIGN KEY (account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
