<?php

return [
    // Opt-in local engines only. No paid provider or remote fallback.
    'text' => [
        'enabled' => (bool) env('KMJ_PRODUCT_TEXT_ENABLED', false),
        'url' => env('KMJ_PRODUCT_OLLAMA_URL', 'http://127.0.0.1:11434'),
        'model' => env('KMJ_PRODUCT_OLLAMA_MODEL', ''),
    ],
    'image' => [
        'enabled' => (bool) env('KMJ_PRODUCT_IMAGE_ENABLED', false),
        'url' => env('KMJ_PRODUCT_SD_URL', 'http://127.0.0.1:7860'),
    ],
];
