<?php

declare(strict_types=1);

return [
    // Remain off until isolated PostgreSQL CI, backup/restore and entitlement
    // integration pass. Production cannot enable it from an AI prompt.
    'enabled' => (bool) env('KMJ_KNOWLEDGE_MEMORY_ENABLED', false),
];
