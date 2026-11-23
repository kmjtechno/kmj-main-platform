<?php

declare(strict_types=1);

return [
    // Owner-approved rollout only. A configured policy is not a license,
    // and an unreviewed deploy must not mutate commercial ledgers.
    'auto_expire_trials' => (bool) env('KMJ_OMNIDESK_AUTO_EXPIRE_TRIALS_ENABLED', false),
    // Explicit product-launch approval. Even if enabled, the active catalog,
    // trial pricing policy, membership and expiry constraints remain mandatory.
    'trial_self_service_enabled' => (bool) env('KMJ_OMNIDESK_TRIAL_SELF_SERVICE_ENABLED', false),
    // Paid plan selection requires explicit approved product/merchant rollout.
    // A plan snapshot alone NEVER authorizes a charge or signed license.
    'paid_plan_binding_enabled' => (bool) env('KMJ_OMNIDESK_PAID_PLAN_BINDING_ENABLED', false),
];
