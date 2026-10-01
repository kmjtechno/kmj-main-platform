<?php

$issuer = rtrim((string) env('CODEBRIDGE_OAUTH_ISSUER', env('APP_URL', 'http://localhost')), '/');

return [
    // Disabled by default: every OAuth endpoint returns 404 until an operator
    // configures the signing key and the CodeBridge MCP resource URL.
    'enabled' => (bool) env('CODEBRIDGE_OAUTH_ENABLED', false),
    'issuer' => $issuer,
    // Exact public URL of the hosted CodeBridge MCP gateway (audience).
    'resource' => (string) env('CODEBRIDGE_OAUTH_RESOURCE', ''),
    // Base64 Ed25519 seed (32 bytes) or secret key (64 bytes). Never commit.
    'signing_key' => env('CODEBRIDGE_OAUTH_SIGNING_KEY'),
    'kid' => (string) env('CODEBRIDGE_OAUTH_KID', 'codebridge-oauth-1'),
    'access_token_ttl' => 900,
    'refresh_token_ttl' => 2592000,
    'code_ttl' => 60,
    'max_redirect_uris' => 10,
];
