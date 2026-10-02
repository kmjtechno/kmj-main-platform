<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\OAuth;

use DomainException;

/**
 * Framework-free OAuth 2.1 primitives for the CodeBridge authorization server.
 *
 * Security-relevant rules live here so they can be unit tested without the
 * framework: PKCE (S256 only), redirect URI registration and matching (exact
 * match, with RFC 8252 port-agnostic loopback), scope parsing, opaque secret
 * generation and Ed25519 (EdDSA) JWT signing.
 */
final class OAuthCore
{
    public const SCOPES = ['openid', 'codebridge:read', 'codebridge:write', 'codebridge:execute', 'offline_access'];

    private const LOOPBACK_HOSTS = ['127.0.0.1', 'localhost', '[::1]'];

    /** RFC 7636 S256: challenge == BASE64URL(SHA256(verifier)). */
    public static function verifyPkce(string $verifier, string $challenge): bool
    {
        if (! preg_match('/\A[A-Za-z0-9\-._~]{43,128}\z/D', $verifier)) {
            return false;
        }
        if (! preg_match('/\A[A-Za-z0-9_-]{43}\z/D', $challenge)) {
            return false;
        }

        return hash_equals($challenge, self::base64Url(hash('sha256', $verifier, true)));
    }

    public static function isValidChallenge(string $challenge): bool
    {
        return (bool) preg_match('/\A[A-Za-z0-9_-]{43}\z/D', $challenge);
    }

    /**
     * A redirect URI may be registered when it is an absolute https URL, or an
     * http loopback URL for native clients (RFC 8252), with no fragment,
     * userinfo, whitespace or control characters.
     */
    public static function isRegistrableRedirect(string $uri): bool
    {
        if ($uri === '' || strlen($uri) > 512 || preg_match('/[\s\x00-\x1F\x7F"<>\\\\]/', $uri)) {
            return false;
        }
        $parts = parse_url($uri);
        if (! is_array($parts) || ! isset($parts['scheme'], $parts['host']) || isset($parts['fragment']) || isset($parts['user']) || isset($parts['pass'])) {
            return false;
        }
        $scheme = strtolower($parts['scheme']);
        $host = strtolower($parts['host']);

        return $scheme === 'https' || ($scheme === 'http' && in_array($host, self::LOOPBACK_HOSTS, true));
    }

    /**
     * Exact string match against a registered URI, except that for http
     * loopback URIs the port is ignored (RFC 8252 section 7.3), as native
     * clients such as Claude Code use an ephemeral port.
     *
     * @param  list<string>  $registered
     */
    public static function redirectMatches(array $registered, string $requested): bool
    {
        foreach ($registered as $candidate) {
            if (hash_equals($candidate, $requested)) {
                return true;
            }
            if (self::isLoopback($candidate) && self::isLoopback($requested)
                && hash_equals(self::withoutPort($candidate), self::withoutPort($requested))) {
                return true;
            }
        }

        return false;
    }

    /** @return list<string> */
    public static function parseScopes(?string $scope): array
    {
        if ($scope === null || trim($scope) === '') {
            return ['codebridge:read'];
        }
        if (strlen($scope) > 512) {
            throw new DomainException('invalid_scope');
        }
        $requested = array_values(array_unique(preg_split('/ +/', trim($scope)) ?: []));
        foreach ($requested as $item) {
            if (! in_array($item, self::SCOPES, true)) {
                throw new DomainException('invalid_scope');
            }
        }

        return $requested;
    }

    /** Opaque, URL-safe secret with 256 bits of entropy. */
    public static function secret(): string
    {
        return self::base64Url(random_bytes(32));
    }

    public static function hashSecret(string $secret): string
    {
        return hash('sha256', $secret);
    }

    /** @param array<string, mixed> $claims */
    public static function signJwt(
        array $claims,
        string $secretKey,
        string $kid,
        string $type = 'at+jwt',
    ): string {
        if (strlen($secretKey) !== SODIUM_CRYPTO_SIGN_SECRETKEYBYTES) {
            throw new DomainException('OAUTH_SIGNING_KEY_INVALID');
        }
        $header = self::base64Url(json_encode(['alg' => 'EdDSA', 'typ' => $type, 'kid' => $kid], JSON_THROW_ON_ERROR));
        $payload = self::base64Url(json_encode($claims, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
        $signature = sodium_crypto_sign_detached($header.'.'.$payload, $secretKey);

        return $header.'.'.$payload.'.'.self::base64Url($signature);
    }

    /** @return array{kty:string,crv:string,x:string,kid:string,alg:string,use:string} */
    public static function publicJwk(string $secretKey, string $kid): array
    {
        if (strlen($secretKey) !== SODIUM_CRYPTO_SIGN_SECRETKEYBYTES) {
            throw new DomainException('OAUTH_SIGNING_KEY_INVALID');
        }

        return [
            'kty' => 'OKP',
            'crv' => 'Ed25519',
            'x' => self::base64Url(sodium_crypto_sign_publickey_from_secretkey($secretKey)),
            'kid' => $kid,
            'alg' => 'EdDSA',
            'use' => 'sig',
        ];
    }

    /** Decodes the base64 (or base64url) configured secret key; returns '' when absent. */
    public static function decodeSigningKey(?string $configured): string
    {
        if ($configured === null || $configured === '') {
            return '';
        }
        $raw = base64_decode(strtr($configured, '-_', '+/'), true);
        if ($raw === false) {
            return '';
        }
        if (strlen($raw) === SODIUM_CRYPTO_SIGN_SEEDBYTES) {
            $raw = sodium_crypto_sign_secretkey(sodium_crypto_sign_seed_keypair($raw));
        }

        return strlen($raw) === SODIUM_CRYPTO_SIGN_SECRETKEYBYTES ? $raw : '';
    }

    public static function base64Url(string $bytes): string
    {
        return rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
    }

    private static function isLoopback(string $uri): bool
    {
        $parts = parse_url($uri);

        return is_array($parts) && strtolower($parts['scheme'] ?? '') === 'http'
            && in_array(strtolower($parts['host'] ?? ''), self::LOOPBACK_HOSTS, true);
    }

    private static function withoutPort(string $uri): string
    {
        $parts = parse_url($uri);

        return strtolower((string) ($parts['host'] ?? '')).($parts['path'] ?? '').(isset($parts['query']) ? '?'.$parts['query'] : '');
    }
}
