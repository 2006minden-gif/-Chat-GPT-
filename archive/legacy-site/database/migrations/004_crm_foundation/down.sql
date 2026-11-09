-- 004 rollback: runner refuses if ANY new table contains data. Legacy tables untouched.
DROP TABLE IF EXISTS nd_activity_history;
DROP TABLE IF EXISTS nd_task_projects;
DROP TABLE IF EXISTS nd_tasks;
DROP TABLE IF EXISTS nd_project_members;
DROP TABLE IF EXISTS nd_project_stages;
DROP TABLE IF EXISTS nd_projects;
DROP TABLE IF EXISTS nd_orders;
DROP TABLE IF EXISTS nd_deals;
DROP TABLE IF EXISTS nd_lead_customers;
DROP TABLE IF EXISTS nd_customer_accounts;
DROP TABLE IF EXISTS nd_employees;
DROP TABLE IF EXISTS nd_customers;
