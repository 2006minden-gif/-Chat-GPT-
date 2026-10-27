-- 004: additive CRM foundation; use scripts/migrate.php, not direct production import.
CREATE TABLE nd_customers (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 kind ENUM('person','company') NOT NULL DEFAULT 'person',
 name VARCHAR(190) NOT NULL,
 email VARCHAR(190) NULL,
 phone VARCHAR(32) NULL,
 telegram VARCHAR(64) NULL,
 notes TEXT NULL,
 status ENUM('active','archived') NOT NULL DEFAULT 'active',
 archived_at DATETIME NULL,
 KEY nd_customers_status (status,id) ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_employees (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(190) NOT NULL,
 email VARCHAR(190) NOT NULL,
 status ENUM('invited','active','suspended','archived') NOT NULL DEFAULT 'invited',
 archived_at DATETIME NULL,
 UNIQUE KEY nd_employees_email (email),
 KEY nd_employees_status (status,id) ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_customer_accounts (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 email VARCHAR(190) NOT NULL,
 password_hash VARCHAR(255) NULL,
 status ENUM('invited','active','disabled') NOT NULL DEFAULT 'invited',
 last_login_at DATETIME NULL,
 UNIQUE KEY nd_customer_accounts_email (email),
 KEY nd_customer_accounts_customer (customer_id,status,id),
 CONSTRAINT nd_ca_customer_fk FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_lead_customers (
 lead_id INT UNSIGNED PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 linked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY nd_lc_customer_lead (customer_id,lead_id),
 CONSTRAINT nd_lc_lead_fk FOREIGN KEY (lead_id) REFERENCES nd_leads(id) ON DELETE RESTRICT,
 CONSTRAINT nd_lc_customer_fk FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_deals (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 lead_id INT UNSIGNED NULL,
 owner_employee_id BIGINT UNSIGNED NULL,
 title VARCHAR(190) NOT NULL,
 status ENUM('new','qualified','proposal','negotiation','won','lost') NOT NULL DEFAULT 'new',
 estimated_amount DECIMAL(15,2) UNSIGNED NULL,
 currency CHAR(3) NOT NULL DEFAULT 'RUB',
 closed_at DATETIME NULL,
 archived_at DATETIME NULL,
 UNIQUE KEY nd_deals_customer_id (customer_id,id),
 KEY nd_deals_owner (owner_employee_id,status,id),
 KEY nd_deals_customer_status (customer_id,status,id),
 KEY nd_deals_source_lead (customer_id,lead_id),
 CONSTRAINT nd_deals_customer_fk FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 CONSTRAINT nd_deals_source_fk FOREIGN KEY (customer_id,lead_id) REFERENCES nd_lead_customers(customer_id,lead_id) ON DELETE RESTRICT,
 CONSTRAINT nd_deals_owner_fk FOREIGN KEY (owner_employee_id) REFERENCES nd_employees(id) ON DELETE RESTRICT ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_orders (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 deal_id BIGINT UNSIGNED NULL,
 number VARCHAR(64) NOT NULL,
 title VARCHAR(190) NOT NULL,
 status ENUM('draft','confirmed','in_progress','completed','cancelled') NOT NULL DEFAULT 'draft',
 total_amount DECIMAL(15,2) UNSIGNED NOT NULL,
 currency CHAR(3) NOT NULL DEFAULT 'RUB',
 confirmed_at DATETIME NULL,
 completed_at DATETIME NULL,
 archived_at DATETIME NULL,
 UNIQUE KEY nd_orders_number (number),
 UNIQUE KEY nd_orders_customer_id (customer_id,id),
 KEY nd_orders_customer_status (customer_id,status,id),
 KEY nd_orders_source_deal (customer_id,deal_id),
 CONSTRAINT nd_orders_customer_fk FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 CONSTRAINT nd_orders_deal_fk FOREIGN KEY (customer_id,deal_id) REFERENCES nd_deals(customer_id,id) ON DELETE RESTRICT ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_projects (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 customer_id BIGINT UNSIGNED NOT NULL,
 order_id BIGINT UNSIGNED NULL,
 manager_employee_id BIGINT UNSIGNED NULL,
 title VARCHAR(190) NOT NULL,
 description TEXT NULL,
 status ENUM('planned','active','on_hold','completed','cancelled') NOT NULL DEFAULT 'planned',
 starts_on DATE NULL,
 due_on DATE NULL,
 completed_at DATETIME NULL,
 archived_at DATETIME NULL,
 KEY nd_projects_customer (customer_id,status,id),
 KEY nd_projects_source_order (customer_id,order_id),
 KEY nd_projects_manager_due (manager_employee_id,status,due_on,id),
 CONSTRAINT nd_projects_customer_fk FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 CONSTRAINT nd_projects_order_fk FOREIGN KEY (customer_id,order_id) REFERENCES nd_orders(customer_id,id) ON DELETE RESTRICT,
 CONSTRAINT nd_projects_manager_fk FOREIGN KEY (manager_employee_id) REFERENCES nd_employees(id) ON DELETE RESTRICT ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_project_stages (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 position INT UNSIGNED NOT NULL,
 title VARCHAR(190) NOT NULL,
 status ENUM('planned','active','completed','cancelled') NOT NULL DEFAULT 'planned',
 due_on DATE NULL,
 completed_at DATETIME NULL,
 UNIQUE KEY nd_stages_position (project_id,position),
 UNIQUE KEY nd_stages_project_id (project_id,id),
 KEY nd_stages_status (project_id,status,id),
 CONSTRAINT nd_stages_project_fk FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_project_members (
 project_id BIGINT UNSIGNED NOT NULL,
 employee_id BIGINT UNSIGNED NOT NULL,
 role ENUM('manager','contributor','observer') NOT NULL DEFAULT 'contributor',
 joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (project_id,employee_id),
 KEY nd_members_employee (employee_id,project_id),
 CONSTRAINT nd_members_project_fk FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 CONSTRAINT nd_members_employee_fk FOREIGN KEY (employee_id) REFERENCES nd_employees(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_tasks (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 assignee_employee_id BIGINT UNSIGNED NULL,
 title VARCHAR(190) NOT NULL,
 description TEXT NULL,
 status ENUM('todo','in_progress','blocked','done','cancelled') NOT NULL DEFAULT 'todo',
 priority ENUM('low','normal','high','urgent') NOT NULL DEFAULT 'normal',
 due_at DATETIME NULL,
 completed_at DATETIME NULL,
 archived_at DATETIME NULL,
 KEY nd_tasks_assignee_due (assignee_employee_id,status,due_at,id),
 KEY nd_tasks_status_due (status,due_at,id),
 CONSTRAINT nd_tasks_assignee_fk FOREIGN KEY (assignee_employee_id) REFERENCES nd_employees(id) ON DELETE RESTRICT ,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 version INT UNSIGNED NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_task_projects (
 task_id BIGINT UNSIGNED PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 stage_id BIGINT UNSIGNED NULL,
 KEY nd_tp_project_stage (project_id,stage_id),
 CONSTRAINT nd_tp_task_fk FOREIGN KEY (task_id) REFERENCES nd_tasks(id) ON DELETE RESTRICT,
 CONSTRAINT nd_tp_project_fk FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 CONSTRAINT nd_tp_stage_fk FOREIGN KEY (project_id,stage_id) REFERENCES nd_project_stages(project_id,id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE nd_activity_history (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 actor_admin_id TINYINT UNSIGNED NULL,
 actor_employee_id BIGINT UNSIGNED NULL,
 actor_customer_account_id BIGINT UNSIGNED NULL,
 employee_id BIGINT UNSIGNED NULL,
 customer_account_id BIGINT UNSIGNED NULL,
 customer_id BIGINT UNSIGNED NULL,
 lead_id INT UNSIGNED NULL,
 deal_id BIGINT UNSIGNED NULL,
 order_id BIGINT UNSIGNED NULL,
 project_id BIGINT UNSIGNED NULL,
 stage_id BIGINT UNSIGNED NULL,
 task_id BIGINT UNSIGNED NULL,
 action VARCHAR(64) NOT NULL,
 summary VARCHAR(500) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY nd_history_time (created_at,id),
 KEY nd_history_subject_employee (employee_id,id),
 KEY nd_history_subject_account (customer_account_id,id),
 KEY nd_history_customer (customer_id,id),
 KEY nd_history_lead (lead_id,id),
 KEY nd_history_deal (deal_id,id),
 KEY nd_history_order (order_id,id),
 KEY nd_history_project (project_id,id),
 KEY nd_history_stage (stage_id,id),
 KEY nd_history_task (task_id,id),
 KEY nd_history_admin (actor_admin_id,id),
 KEY nd_history_employee (actor_employee_id,id),
 KEY nd_history_account (actor_customer_account_id,id),
 CONSTRAINT nd_history_subject_employee_fk FOREIGN KEY (employee_id) REFERENCES nd_employees(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_subject_account_fk FOREIGN KEY (customer_account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_admin_fk FOREIGN KEY (actor_admin_id) REFERENCES nd_admin(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_employee_fk FOREIGN KEY (actor_employee_id) REFERENCES nd_employees(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_account_fk FOREIGN KEY (actor_customer_account_id) REFERENCES nd_customer_accounts(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_customer_fk FOREIGN KEY (customer_id) REFERENCES nd_customers(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_lead_fk FOREIGN KEY (lead_id) REFERENCES nd_leads(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_deal_fk FOREIGN KEY (deal_id) REFERENCES nd_deals(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_order_fk FOREIGN KEY (order_id) REFERENCES nd_orders(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_project_fk FOREIGN KEY (project_id) REFERENCES nd_projects(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_stage_fk FOREIGN KEY (stage_id) REFERENCES nd_project_stages(id) ON DELETE RESTRICT,
 CONSTRAINT nd_history_task_fk FOREIGN KEY (task_id) REFERENCES nd_tasks(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
