<?php
// Copy to config.php OUTSIDE the site's public directory. Never upload into public_html.
return [
    'db_host' => 'localhost',
    'db_port' => 3306,
    'db_name' => 'YOUR_DATABASE',
    'db_user' => 'YOUR_DATABASE_USER',
    'db_password' => 'YOUR_DATABASE_PASSWORD',
    'app_url' => 'https://neurodelo.pro',
    // Invent a separate random secret of at least 32 characters for first installation.
    // After installation remove this value and delete public/setup.php.
    'setup_key' => '',
    // Enable only after owner/legal review; place approved text in private/privacy-policy.txt.
    'privacy_policy_approved' => false,
    'privacy_policy_version' => '',
    // Keep both false until Stage 3/4 migrations, mail and customer/invitation legal review pass.
    'customer_auth_enabled' => false,
    'customer_auth_privacy_approved' => false,
    // SMTP acceptance is not guaranteed inbox delivery. Store actual credentials only in config.php.
    'customer_mail' => [
        'transport' => 'smtp', 'host' => '', 'port' => 587, 'encryption' => 'starttls',
        'from' => '', 'username' => '', 'password' => '',
    ],
];
