<?php
// Copy to config.php OUTSIDE the site's public directory. Never upload into public_html.
return [
    'db_host' => 'localhost',
    'db_port' => 3306,
    'db_name' => 'YOUR_DATABASE',
    'db_user' => 'YOUR_DATABASE_USER',
    'db_password' => 'YOUR_DATABASE_PASSWORD',
    'app_url' => 'https://neurodelo.pro',
    // First login happens ONLY via the personal one-time link sent to the client
    // after payment: /owner-setup.php#token=... (see docs/OWNER-FIRST-LOGIN.md).
    // There is no public setup form; do not add one back.
    // Enable only after owner/legal review; place approved text in private/privacy-policy.txt.
    'privacy_policy_approved' => false,
    'privacy_policy_version' => '',
];
