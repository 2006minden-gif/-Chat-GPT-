-- Additive operations data only. Apply exclusively with the CLI runner after approval.
ALTER TABLE nd_deals ADD due_on DATE NULL, ADD loss_reason VARCHAR(500) NULL;
ALTER TABLE nd_orders ADD due_on DATE NULL, ADD notes TEXT NULL;
ALTER TABLE nd_employees ADD position VARCHAR(190) NULL;
CREATE TABLE nd_crm_requests (
 request_key CHAR(64) PRIMARY KEY,
 request_hash CHAR(64) NOT NULL,
 result TEXT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_crm_conversions (
 deal_id BIGINT UNSIGNED PRIMARY KEY,
 order_id BIGINT UNSIGNED NOT NULL UNIQUE,
 FOREIGN KEY (deal_id) REFERENCES nd_deals(id) ON DELETE RESTRICT,
 FOREIGN KEY (order_id) REFERENCES nd_orders(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_crm_notifications (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 event_key VARCHAR(190) NOT NULL UNIQUE,
 entity VARCHAR(32) NOT NULL,
 record_id BIGINT UNSIGNED NOT NULL,
 message VARCHAR(190) NOT NULL,
 read_at DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_notice_unread (read_at,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
