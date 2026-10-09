<?php

return [
    // Source of truth is encrypted server configuration; never expose secrets to Inertia.
    // This config alone MUST NOT authorize charges or entitlement issuance.
    'live_charging_enabled' => (bool) env('KMJ_PAYMENT_LIVE_CHARGING_ENABLED', false),
    'providers' => [
        'razorpay' => [
            'client_id' => env('KMJ_RAZORPAY_KEY_ID'),
            'client_secret' => env('KMJ_RAZORPAY_KEY_SECRET'),
            'webhook_secret' => env('KMJ_RAZORPAY_WEBHOOK_SECRET'),
            'international_approved' => (bool) env('KMJ_RAZORPAY_INTERNATIONAL_APPROVED', false),
        ],
        'cashfree' => [
            'client_id' => env('KMJ_CASHFREE_CLIENT_ID'),
            'client_secret' => env('KMJ_CASHFREE_CLIENT_SECRET'),
            'international_approved' => (bool) env('KMJ_CASHFREE_INTERNATIONAL_APPROVED', false),
        ],
    ],
];
