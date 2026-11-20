<?php

return [
    // Kill switch for the SecurityHeaders middleware (response-only, never overrides a controller's own header).
    'enabled' => filter_var(env('SECURITY_HEADERS_ENABLED', true), FILTER_VALIDATE_BOOLEAN),
];
