-- Original pre-fix lead schema, isolated migration fixture.
CREATE TABLE IF NOT EXISTS nd_leads_legacy (
 id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(100) NOT NULL,
 contact VARCHAR(200) NOT NULL,
 service VARCHAR(100) NOT NULL,
 idea TEXT NOT NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'Новая',
 notes TEXT NOT NULL,
 next_step VARCHAR(500) NOT NULL DEFAULT '',
 created BIGINT UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
