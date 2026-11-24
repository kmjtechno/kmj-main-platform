<?php

return [
    'enabled' => (bool) env('CODEBRIDGE_LICENSE_API_ENABLED', false),
    // Private Elite loopback reader only. Never pass this token to the browser.
    'dashboard_presence_enabled' => (bool) env('CODEBRIDGE_DASHBOARD_PRESENCE_ENABLED', false),
    'dashboard_presence_token' => env('CODEBRIDGE_DASHBOARD_PRESENCE_TOKEN', ''),
    // Fail closed: the workspace may queue approved named tool requests only after an operator
    // turns this on AND a device agent that consumes them is deployed. Default off.
    'workspace_jobs_enabled' => (bool) env('CODEBRIDGE_WORKSPACE_JOBS_ENABLED', false),
];
