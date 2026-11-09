-- One contextual link to existing entities; no duplicate customer/order/auth model.
CREATE TABLE nd_lc_inquiry_orders (
 lead_id INT UNSIGNED PRIMARY KEY,
 order_id BIGINT UNSIGNED NOT NULL UNIQUE,
 project_id BIGINT UNSIGNED NOT NULL UNIQUE,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (lead_id) REFERENCES nd_leads(id) ON DELETE RESTRICT,
 FOREIGN KEY (order_id) REFERENCES nd_orders(id) ON DELETE RESTRICT,
 FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
