<?php

return [
    // ADR-004: cloud-only, fresh zero-price evidence, never a paid fallback.
    'text' => [
        'enabled' => (bool) env('KMJ_PRODUCT_TEXT_ENABLED', false),
        'api_key' => env('OPENROUTER_API_KEY', ''),
        'model' => env('KMJ_PRODUCT_CLOUD_MODEL', 'openrouter/free'),
    ],
];
