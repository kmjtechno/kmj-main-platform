<?php

declare(strict_types=1);

return [
    /*
     * This is an identity allowlist, never a grant of privileges.
     *
     * The single intended Super Admin email was confirmed by the owner.
     * The account must STILL hold its existing is_platform_owner grant,
     * verified email, passkey and password-confirmed session.
     *
     * Operators can override this identity only through server-controlled
     * configuration/deployment (not a client request).
     */
    'owner_email' => env('KMJ_SUPER_ADMIN_EMAIL', 'kmjtechno.net@gmail.com'),
    // Explicit, temporary deployment-time approval; never enabled by default.
    'bootstrap_enabled' => (bool) env('KMJ_SUPER_ADMIN_BOOTSTRAP_ENABLED', false),
];
