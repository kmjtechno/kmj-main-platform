<?php

declare(strict_types=1);

return [
    // Explicit owner opt-in only after security, storage and delivery review.
    'enabled' => (bool) env('KMJ_MAIL_INBOUND_PILOT_ENABLED', false),
    'owner_id' => (int) env('KMJ_MAIL_INBOUND_PILOT_OWNER_ID', 0),
    'secret_hex' => env('KMJ_MAIL_INBOUND_PILOT_SECRET_HEX', ''),
    'recipient' => 'mail-pilot@kmjtechno.com',
];
