<?php
// Copy to config.php OUTSIDE the site's public directory. Never upload into public_html.
return [
    // Stage 5 stays disabled until legal approval, migrations and review.
    'crm_operations_enabled' => false,
    // Stage 8. No live adapter until documented API and processing approval.
    'ai_enabled' => false, 'ai_public_enabled' => false, 'ai_data_processing_approved' => false,
    'ai_catalog_approved' => false, 'ai_service_catalog' => [],
    'ai_periodic_authorized' => false,
    'ai_pricing_enabled' => false, 'ai_pricing_auto_enabled' => false,
    'ai_daily_requests' => 20, 'ai_monthly_requests' => 100,
    'ai_daily_tokens' => 50000, 'ai_daily_estimated_micro' => 1000000,
    'ai_provider' => ['enabled' => false, 'type' => '', 'model' => '', 'secret_reference' => '',
        'timeout_seconds' => 10, 'max_tokens' => 2048, 'cost_currency' => '',
        'estimated_micro_per_1000_tokens' => null],
    // Stage 7: no live payment adapter; activation requires separate legal/provider review.
    'billing_enabled' => false,
    'billing_email_enabled' => false,
    'billing_owner_email' => '',
    'billing_merchant' => [
        'approved' => false, 'legal_name' => '', 'registration' => '', 'address' => '',
        'tax_treatment' => '', 'payment_instructions' => '', 'retention_policy' => '', 'number_prefix' => 'ND',
    ],
    'billing_provider' => [
        'enabled' => false, 'sandbox_approved' => false, 'name' => 'yookassa', 'mode' => 'sandbox', 'shop_id' => '', 'secret_key' => '',
    ],
    // Stage 6 is separately gated; content remains outside public_html.
    'client_collaboration_enabled' => false,
    'collaboration_file_max_bytes' => 5242880,
    'collaboration_total_max_bytes' => 104857600,
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
