<?php

declare(strict_types=1);

return [
    // Read-only single-owner pilot. Do not use an administrator-wide token.
    // Never put values in Git, browser props, command arguments or logs.
    'pilot_enabled' => (bool) env('KMJ_MAIL_ENGINE_PILOT_ENABLED', false),
    'pilot_owner_id' => (int) env('KMJ_MAIL_ENGINE_PILOT_OWNER_ID', 0),
    'pilot_username' => env('KMJ_MAIL_ENGINE_PILOT_USERNAME', ''),
    'pilot_access_token' => env('KMJ_MAIL_ENGINE_PILOT_ACCESS_TOKEN', ''),
];
