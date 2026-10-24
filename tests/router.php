<?php
// Only for PHP's local development server. Production uses public/.htaccess.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$allowed = ['/', '/index.php', '/studio.php', '/setup.php', '/api.php', '/styles.css', '/script.js', '/crm.css', '/crm.js', '/api-client.js', '/privacy.php', '/customer.php', '/customer-api.php', '/customer.js', '/customer.css', '/customer-owner.js', '/workspace.php', '/operations.css', '/operations.js', '/portal.php', '/portal.js'];
if (!in_array($path, $allowed, true)) { http_response_code(404); exit; }
return false;
