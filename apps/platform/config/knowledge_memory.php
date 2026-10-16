<?php

declare(strict_types=1);

return [
    // Remain off until isolated PostgreSQL CI, backup/restore and entitlement
    // integration pass. Production cannot enable it from an AI prompt.
    'enabled' => (bool) env('KMJ_KNOWLEDGE_MEMORY_ENABLED', false),

    // Initial explicit grant only; no project auto-discovery, aliases or
    // cross-repository reads. Enabling additional projects needs review.
    'project' => 'kmj-codebridge',
];
