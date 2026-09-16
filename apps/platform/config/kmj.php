<?php

return [
    'staging_admin_password' => env('KMJ_STAGING_ADMIN_PASSWORD'),

    'ops' => [
        'backup_status_dir' => env('KMJ_BACKUP_STATUS_DIR', storage_path('app/private/ops')),
        'delivery_status_path' => env('KMJ_DELIVERY_STATUS_PATH', '/var/tmp/kmj-delivery-control/status.json'),
        'delivery_status_max_age_seconds' => (int) env('KMJ_DELIVERY_STATUS_MAX_AGE_SECONDS', 600),
        'control_request_path' => env('KMJ_CONTROL_REQUEST_PATH', storage_path('app/private/ops/control-request.json')),
        'backup_freshness_hours' => [
            'daily' => 36,
            'weekly' => 216,
            'monthly' => 840,
        ],
        'guardrails' => [
            // Internal KMJ operational guardrails, not hosting-provider legal limits.
            'resource_warning_percent' => 85,
            'resource_critical_percent' => 95,
        ],
        'worker_execution_enabled' => env('KMJ_EXECUTION_ENABLED'),
        'worker_write_enabled' => env('KMJ_AUTONOMOUS_WRITE_ENABLED'),
        'free_ai_provider_credentials' => [
            '9router' => env('KMJ_9ROUTER_API_KEY'),
            'openrouter' => env('OPENROUTER_API_KEY'),
            'groq' => env('GROQ_API_KEY'),
            'cerebras' => env('CEREBRAS_API_KEY'),
            'mistral' => env('MISTRAL_API_KEY'),
            'gemini' => env('GEMINI_API_KEY'),
        ],
    ],
];
