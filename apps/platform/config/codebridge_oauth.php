<?php

$appUrl = rtrim((string) env('APP_URL', 'http://localhost'), '/');
$issuer = rtrim((string) env('CODEBRIDGE_OAUTH_ISSUER', $appUrl), '/');
$isProduction = (string) env('APP_ENV', 'local') === 'production';

$signingKey = env('CODEBRIDGE_OAUTH_SIGNING_KEY');
if (($signingKey === null || $signingKey === '') && $isProduction) {
    $appKey = (string) env('APP_KEY', '');
    $rawAppKey = str_starts_with($appKey, 'base64:')
        ? base64_decode(substr($appKey, 7), true)
        : $appKey;

    if (is_string($rawAppKey) && strlen($rawAppKey) >= 32) {
        // Domain-separated deterministic seed. This avoids reusing APP_KEY bytes
        // directly while allowing existing production installs to boot OAuth
        // without a second secret. A dedicated key remains the preferred override.
        $seed = hash_hmac('sha256', 'kmj-codebridge-oauth-ed25519-v1', $rawAppKey, true);
        $signingKey = base64_encode($seed);
    }
}

return [
    'enabled' => filter_var(
        env('CODEBRIDGE_OAUTH_ENABLED', $isProduction),
        FILTER_VALIDATE_BOOL,
    ),
    'issuer' => $issuer,
    // Hosted Main Platform and CodeBridge share the public origin in production.
    'resource' => (string) env('CODEBRIDGE_OAUTH_RESOURCE', $issuer.'/mcp'),
    // Base64 Ed25519 seed (32 bytes) or secret key (64 bytes).
    'signing_key' => $signingKey,
    'kid' => (string) env('CODEBRIDGE_OAUTH_KID', 'codebridge-oauth-1'),
    'access_token_ttl' => 900,
    'refresh_token_ttl' => 2592000,
    'code_ttl' => 60,
    'max_redirect_uris' => 10,
];
