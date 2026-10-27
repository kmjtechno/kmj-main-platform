<?php

return [
    // ADR-004: cloud-only, fresh zero-price evidence, never a paid fallback.
    'text' => [
        'enabled' => (bool) env('KMJ_PRODUCT_TEXT_ENABLED', false),
        'api_key' => env('OPENROUTER_API_KEY', ''),
        'model' => env('KMJ_PRODUCT_CLOUD_MODEL', 'openrouter/free'),
    ],
    // Disabled until the operator independently confirms a Workers FREE plan.
    // Workers Paid may bill overages: never auto-enable, upgrade or fall back.
    'image' => [
        'enabled' => (bool) env('KMJ_PRODUCT_IMAGE_ENABLED', false),
        'free_account_attested' => (bool) env('KMJ_CF_WORKERS_FREE_PLAN_ATTESTED', false),
        'account_id' => env('KMJ_CF_AI_ACCOUNT_ID', ''),
        'api_token' => env('KMJ_CF_AI_TOKEN', ''),
        'max_daily_requests' => 2,
    ],
];
