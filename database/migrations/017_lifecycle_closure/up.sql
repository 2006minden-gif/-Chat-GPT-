CREATE TABLE nd_lc_closure_records (
 order_id BIGINT UNSIGNED PRIMARY KEY,
 acceptance_binding_id BIGINT UNSIGNED NULL,
 handover_binding_id BIGINT UNSIGNED NULL,
 closure_snapshot MEDIUMTEXT NULL,
 unresolved_snapshot MEDIUMTEXT NULL,
 override_reason TEXT NULL,
 closed_by TINYINT UNSIGNED NULL,
 closed_at DATETIME NULL,
 version INT UNSIGNED NOT NULL DEFAULT 1,
 FOREIGN KEY (order_id) REFERENCES nd_lc_order_flow(order_id) ON DELETE RESTRICT,
 FOREIGN KEY (acceptance_binding_id) REFERENCES nd_lc_document_bindings(id) ON DELETE RESTRICT,
 FOREIGN KEY (handover_binding_id) REFERENCES nd_lc_document_bindings(id) ON DELETE RESTRICT,
 FOREIGN KEY (closed_by) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE nd_lc_change_applications (
 change_id BIGINT UNSIGNED PRIMARY KEY,
 signed_binding_id BIGINT UNSIGNED NOT NULL UNIQUE,
 previous_binding_id BIGINT UNSIGNED NOT NULL,
 previous_price_minor BIGINT UNSIGNED NOT NULL,
 revised_price_minor BIGINT UNSIGNED NOT NULL,
 credited_actual_income_minor BIGINT UNSIGNED NOT NULL,
 invoice_snapshot MEDIUMTEXT NOT NULL,
 new_invoice_ids MEDIUMTEXT NOT NULL,
 applied_by TINYINT UNSIGNED NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (change_id) REFERENCES nd_lc_scope_changes(id) ON DELETE RESTRICT,
 FOREIGN KEY (signed_binding_id) REFERENCES nd_lc_document_bindings(id) ON DELETE RESTRICT,
 FOREIGN KEY (previous_binding_id) REFERENCES nd_lc_document_bindings(id) ON DELETE RESTRICT,
 FOREIGN KEY (applied_by) REFERENCES nd_admin(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
