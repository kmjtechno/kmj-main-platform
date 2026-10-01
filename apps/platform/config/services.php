<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Resend, Postmark, AWS, and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'key' => env('POSTMARK_API_KEY'),
    ],

    'resend' => [
        'key' => env('RESEND_API_KEY'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    'kmj_sandbox_licensing' => [
        'secret' => env('KMJ_SANDBOX_LICENSE_SECRET'),
        'validation_engine' => env('KMJ_SANDBOX_LICENSE_VALIDATION_ENGINE', 'php'),
        'rust_verifier_binary' => env('KMJ_SANDBOX_RUST_VERIFIER_BINARY', ''),
        'rust_verifier_timeout' => (float) env('KMJ_SANDBOX_RUST_VERIFIER_TIMEOUT', 5),
    ],

    'codebridge_oauth' => [
        'link_secret' => env('CODEBRIDGE_OAUTH_LINK_SECRET'),
    ],

];
