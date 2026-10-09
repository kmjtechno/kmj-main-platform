<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

final class LegacyMcpOAuthChallenge
{
    /**
     * Extract only a verified, permitted scope from an old CodeBridge HTTP 200
     * tool-level OAuth denial. Never forward an upstream-controlled header.
     */
    public static function scope(string $body, string $resource): ?string
    {
        if (strlen($body) > 16384) {
            return null;
        }

        $message = json_decode($body, true);
        if (! is_array($message) || ($message['jsonrpc'] ?? null) !== '2.0') {
            return null;
        }

        $result = $message['result'] ?? null;
        if (! is_array($result) || ($result['isError'] ?? null) !== true) {
            return null;
        }

        $content = $result['content'] ?? null;
        if (! is_array($content) || count($content) !== 1 || ! is_array($content[0])) {
            return null;
        }

        $text = $content[0]['text'] ?? null;
        if (! is_string($text) || strlen($text) > 512) {
            return null;
        }
        $error = json_decode($text, true);
        if ($error !== ['error' => 'UNAUTHORIZED']) {
            return null;
        }

        $challenge = $result['_meta']['mcp/www_authenticate'][0] ?? null;
        if (! is_string($challenge) || strlen($challenge) > 1024
            || str_contains($challenge, "\r") || str_contains($challenge, "\n")) {
            return null;
        }

        $parts = parse_url($resource);
        if (! is_array($parts) || ($parts['scheme'] ?? null) !== 'https'
            || ! is_string($parts['host'] ?? null)) {
            return null;
        }
        $origin = 'https://'.$parts['host'];
        if (isset($parts['port'])) {
            $origin .= ':'.$parts['port'];
        }
        $metadata = $origin.'/.well-known/oauth-protected-resource';
        if (! str_starts_with($challenge, 'Bearer ')
            || ! str_contains($challenge, 'resource_metadata="'.$metadata.'"')
            || preg_match('/(?:^|,\s*)scope="codebridge:(read|write|execute)"/D', $challenge, $matches) !== 1) {
            return null;
        }

        return 'codebridge:'.$matches[1];
    }

    /**
     * Build a trusted challenge from the Main Platform OAuth resource, not from
     * the legacy upstream's arbitrary HTTP or tool-result headers.
     */
    public static function header(string $resource, string $scope): string
    {
        $parts = parse_url($resource);
        $origin = 'https://'.$parts['host'];
        if (isset($parts['port'])) {
            $origin .= ':'.$parts['port'];
        }

        return 'Bearer resource_metadata="'.$origin.'/.well-known/oauth-protected-resource", scope="'.$scope.'", error="invalid_token"';
    }
}
