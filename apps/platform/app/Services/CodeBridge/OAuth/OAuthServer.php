<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\OAuth;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * OAuth 2.1 authorization server for the hosted CodeBridge MCP gateway.
 *
 * Public clients only (DCR, token_endpoint_auth_method "none"), authorization
 * code + PKCE S256, RFC 8707 resource binding, Ed25519 JWT access tokens with
 * the CodeBridge resource as audience, and rotating refresh tokens with reuse
 * detection that revokes the whole token family.
 */
final class OAuthServer
{
    public function enabled(): bool
    {
        return (bool) config('codebridge_oauth.enabled')
            && $this->resource() !== ''
            && $this->signingKey() !== '';
    }

    public function issuer(): string
    {
        return (string) config('codebridge_oauth.issuer');
    }

    public function resource(): string
    {
        return (string) config('codebridge_oauth.resource');
    }

    /** @return array<string, mixed> RFC 8414 metadata */
    public function metadata(): array
    {
        $issuer = $this->issuer();

        return [
            'issuer' => $issuer,
            'authorization_endpoint' => $issuer.'/oauth/authorize',
            'token_endpoint' => $issuer.'/oauth/token',
            'registration_endpoint' => $issuer.'/oauth/register',
            'jwks_uri' => $issuer.'/oauth/jwks.json',
            'userinfo_endpoint' => $issuer.'/oauth/userinfo',
            'scopes_supported' => OAuthCore::SCOPES,
            'response_types_supported' => ['code'],
            'response_modes_supported' => ['query'],
            'grant_types_supported' => ['authorization_code', 'refresh_token'],
            'token_endpoint_auth_methods_supported' => ['none'],
            'code_challenge_methods_supported' => ['S256'],
            'authorization_response_iss_parameter_supported' => true,
            'service_documentation' => 'https://github.com/kmjtechno/kmj-codebridge/blob/main/docs/CLIENTS.md',
        ];
    }

    /** @return array{keys: list<array<string, string>>} */
    public function jwks(): array
    {
        return ['keys' => [OAuthCore::publicJwk($this->signingKey(), (string) config('codebridge_oauth.kid'))]];
    }

    /**
     * RFC 7591 dynamic registration of a public client.
     *
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    public function register(array $input): array
    {
        $uris = $input['redirect_uris'] ?? null;
        if (! is_array($uris) || $uris === [] || count($uris) > (int) config('codebridge_oauth.max_redirect_uris')) {
            throw new OAuthError('invalid_redirect_uri', 400);
        }
        foreach ($uris as $uri) {
            if (! is_string($uri) || ! OAuthCore::isRegistrableRedirect($uri)) {
                throw new OAuthError('invalid_redirect_uri', 400);
            }
        }
        $method = $input['token_endpoint_auth_method'] ?? 'none';
        if ($method !== 'none') {
            throw new OAuthError('invalid_client_metadata', 400);
        }
        foreach (['grant_types' => ['authorization_code', 'refresh_token'], 'response_types' => ['code']] as $key => $allowed) {
            if (isset($input[$key]) && (! is_array($input[$key]) || array_diff($input[$key], $allowed) !== [])) {
                throw new OAuthError('invalid_client_metadata', 400);
            }
        }
        $name = is_string($input['client_name'] ?? null) ? trim(preg_replace('/[\x00-\x1F\x7F]/', '', $input['client_name']) ?? '') : '';
        $name = $name === '' ? 'MCP client' : mb_substr($name, 0, 120);
        $clientId = 'cb_'.Str::lower(Str::random(40));
        $uris = array_values(array_unique($uris));

        DB::table('codebridge_oauth_clients')->insert([
            'client_id' => $clientId,
            'client_name' => $name,
            'redirect_uris' => json_encode($uris, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return [
            'client_id' => $clientId,
            'client_id_issued_at' => time(),
            'client_name' => $name,
            'redirect_uris' => $uris,
            'token_endpoint_auth_method' => 'none',
            'grant_types' => ['authorization_code', 'refresh_token'],
            'response_types' => ['code'],
        ];
    }

    /**
     * Validates an authorization request. Errors about the client or redirect
     * URI must never redirect (they are shown to the user); others redirect.
     *
     * @param  array<string, mixed>  $query
     * @return array{client_id:string,client_name:string,redirect_uri:string,redirect_host:string,scopes:list<string>,state:?string,code_challenge:string,resource:string}
     */
    public function validateAuthorization(array $query): array
    {
        $clientId = is_string($query['client_id'] ?? null) ? $query['client_id'] : '';
        $client = $clientId === '' ? null : DB::table('codebridge_oauth_clients')->where('client_id', $clientId)->first();
        if (! $client) {
            throw new OAuthError('invalid_client', 400);
        }
        $redirect = is_string($query['redirect_uri'] ?? null) ? $query['redirect_uri'] : '';
        $registered = json_decode((string) $client->redirect_uris, true, 4, JSON_THROW_ON_ERROR);
        if ($redirect === '' || ! OAuthCore::redirectMatches($registered, $redirect)) {
            throw new OAuthError('invalid_redirect_uri', 400);
        }
        $state = isset($query['state']) && is_string($query['state']) ? mb_substr($query['state'], 0, 512) : null;

        $redirectError = fn (string $error) => new OAuthError($error, 302, $redirect, $state);
        if (($query['response_type'] ?? null) !== 'code') {
            throw $redirectError('unsupported_response_type');
        }
        if (($query['code_challenge_method'] ?? null) !== 'S256' || ! is_string($query['code_challenge'] ?? null) || ! OAuthCore::isValidChallenge($query['code_challenge'])) {
            throw $redirectError('invalid_request');
        }
        $resource = $query['resource'] ?? $this->resource();
        if (! is_string($resource) || $resource !== $this->resource()) {
            throw $redirectError('invalid_target');
        }
        try {
            $scopes = OAuthCore::parseScopes(is_string($query['scope'] ?? null) ? $query['scope'] : null);
        } catch (DomainException) {
            throw $redirectError('invalid_scope');
        }

        return [
            'client_id' => $clientId,
            'client_name' => (string) $client->client_name,
            'redirect_uri' => $redirect,
            'redirect_host' => (string) parse_url($redirect, PHP_URL_HOST),
            'scopes' => $scopes,
            'state' => $state,
            'code_challenge' => $query['code_challenge'],
            'resource' => $resource,
        ];
    }

    /** @param array{client_id:string,redirect_uri:string,scopes:list<string>,state:?string,code_challenge:string,resource:string} $request */
    public function approve(array $request, int $userId): string
    {
        $code = OAuthCore::secret();
        DB::table('codebridge_oauth_codes')->insert([
            'code_hash' => OAuthCore::hashSecret($code),
            'client_id' => $request['client_id'],
            'user_id' => $userId,
            'redirect_uri' => $request['redirect_uri'],
            'code_challenge' => $request['code_challenge'],
            'scope' => implode(' ', $request['scopes']),
            'resource' => $request['resource'],
            'expires_at_epoch' => time() + (int) config('codebridge_oauth.code_ttl'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $this->redirectWith($request['redirect_uri'], ['code' => $code, 'state' => $request['state'], 'iss' => $this->issuer()]);
    }

    /** @param array{redirect_uri:string,state:?string} $request */
    public function deny(array $request): string
    {
        return $this->redirectWith($request['redirect_uri'], ['error' => 'access_denied', 'state' => $request['state'], 'iss' => $this->issuer()]);
    }

    /**
     * @param  array<string, mixed>  $input  form parameters of the token request
     * @return array<string, mixed>
     */
    public function token(array $input): array
    {
        return match ($input['grant_type'] ?? null) {
            'authorization_code' => $this->exchangeCode($input),
            'refresh_token' => $this->refresh($input),
            default => throw new OAuthError('unsupported_grant_type', 400),
        };
    }

    /**
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    private function exchangeCode(array $input): array
    {
        foreach (['code', 'client_id', 'redirect_uri', 'code_verifier'] as $key) {
            if (! is_string($input[$key] ?? null) || $input[$key] === '') {
                throw new OAuthError('invalid_request', 400);
            }
        }
        $now = time();

        return DB::transaction(function () use ($input, $now): array {
            $row = DB::table('codebridge_oauth_codes')->where('code_hash', OAuthCore::hashSecret($input['code']))->lockForUpdate()->first();
            if (! $row || $row->consumed_at_epoch !== null || (int) $row->expires_at_epoch <= $now
                || ! hash_equals((string) $row->client_id, $input['client_id'])
                || ! hash_equals((string) $row->redirect_uri, $input['redirect_uri'])
                || ! OAuthCore::verifyPkce($input['code_verifier'], (string) $row->code_challenge)) {
                throw new OAuthError('invalid_grant', 400);
            }
            if (isset($input['resource']) && $input['resource'] !== $row->resource) {
                throw new OAuthError('invalid_target', 400);
            }
            DB::table('codebridge_oauth_codes')->where('code_hash', $row->code_hash)->update(['consumed_at_epoch' => $now, 'updated_at' => now()]);

            return $this->issueTokens((string) $row->client_id, (int) $row->user_id, (string) $row->scope, (string) $row->resource, (string) Str::uuid(), $now);
        }, 3);
    }

    /**
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    private function refresh(array $input): array
    {
        if (! is_string($input['refresh_token'] ?? null) || ! is_string($input['client_id'] ?? null)) {
            throw new OAuthError('invalid_request', 400);
        }
        $now = time();

        $result = DB::transaction(function () use ($input, $now): ?array {
            $row = DB::table('codebridge_oauth_refresh_tokens')->where('token_hash', OAuthCore::hashSecret($input['refresh_token']))->lockForUpdate()->first();
            if (! $row || ! hash_equals((string) $row->client_id, $input['client_id'])) {
                throw new OAuthError('invalid_grant', 400);
            }
            if ($row->rotated_at_epoch !== null) {
                // Reuse of a rotated token: assume theft and revoke the family.
                // Returned (not thrown) so the revocation commits.
                DB::table('codebridge_oauth_refresh_tokens')->where('family_id', $row->family_id)->whereNull('revoked_at_epoch')->update(['revoked_at_epoch' => $now, 'updated_at' => now()]);

                return null;
            }
            if ($row->revoked_at_epoch !== null || (int) $row->expires_at_epoch <= $now) {
                throw new OAuthError('invalid_grant', 400);
            }
            $scope = (string) $row->scope;
            if (is_string($input['scope'] ?? null) && $input['scope'] !== '') {
                try {
                    $requested = OAuthCore::parseScopes($input['scope']);
                } catch (DomainException) {
                    throw new OAuthError('invalid_scope', 400);
                }
                if (array_diff($requested, explode(' ', $scope)) !== []) {
                    throw new OAuthError('invalid_scope', 400);
                }
                $scope = implode(' ', $requested);
            }
            DB::table('codebridge_oauth_refresh_tokens')->where('token_hash', $row->token_hash)->update(['rotated_at_epoch' => $now, 'updated_at' => now()]);

            return $this->issueTokens((string) $row->client_id, (int) $row->user_id, $scope, (string) $row->resource, (string) $row->family_id, $now);
        }, 3);
        if ($result === null) {
            throw new OAuthError('invalid_grant', 400);
        }

        return $result;
    }

    /** @return array<string, mixed> */
    private function issueTokens(string $clientId, int $userId, string $scope, string $resource, string $family, int $now): array
    {
        $ttl = (int) config('codebridge_oauth.access_token_ttl');
        $accessScope = implode(' ', array_values(array_diff(explode(' ', $scope), ['offline_access'])));
        $access = OAuthCore::signJwt([
            'iss' => $this->issuer(),
            'aud' => $resource,
            'sub' => 'kmj-user:'.$userId,
            'client_id' => $clientId,
            'scope' => $accessScope,
            'iat' => $now,
            'nbf' => $now,
            'exp' => $now + $ttl,
            'jti' => (string) Str::uuid(),
        ], $this->signingKey(), (string) config('codebridge_oauth.kid'));

        $refresh = OAuthCore::secret();
        DB::table('codebridge_oauth_refresh_tokens')->insert([
            'token_hash' => OAuthCore::hashSecret($refresh),
            'family_id' => $family,
            'client_id' => $clientId,
            'user_id' => $userId,
            'scope' => $scope,
            'resource' => $resource,
            'expires_at_epoch' => $now + (int) config('codebridge_oauth.refresh_token_ttl'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return [
            'access_token' => $access,
            'token_type' => 'Bearer',
            'expires_in' => $ttl,
            'refresh_token' => $refresh,
            'scope' => $accessScope,
        ];
    }

    /**
     * Verify a CodeBridge OAuth access token issued by this server.
     *
     * @return array<string, mixed>|null
     */
    public function verifyAccessToken(string $token, ?int $now = null): ?array
    {
        if (! $this->enabled() || strlen($token) > 16384) {
            return null;
        }

        $parts = explode('.', $token);
        if (count($parts) !== 3) {
            return null;
        }

        try {
            $header = json_decode($this->decodeBase64Url($parts[0]), true, 16, JSON_THROW_ON_ERROR);
            $claims = json_decode($this->decodeBase64Url($parts[1]), true, 32, JSON_THROW_ON_ERROR);
            $signature = $this->decodeBase64Url($parts[2]);
        } catch (\Throwable) {
            return null;
        }

        if (! is_array($header) || ! is_array($claims)
            || ($header['alg'] ?? null) !== 'EdDSA'
            || ($header['typ'] ?? null) !== 'at+jwt'
            || ($header['kid'] ?? null) !== (string) config('codebridge_oauth.kid')) {
            return null;
        }

        $secret = $this->signingKey();
        if ($secret === '' || strlen($signature) !== SODIUM_CRYPTO_SIGN_BYTES) {
            return null;
        }
        $public = sodium_crypto_sign_publickey_from_secretkey($secret);
        if (! sodium_crypto_sign_verify_detached($signature, $parts[0].'.'.$parts[1], $public)) {
            return null;
        }

        $now ??= time();
        if (($claims['iss'] ?? null) !== $this->issuer()
            || ($claims['aud'] ?? null) !== $this->resource()
            || ! is_string($claims['sub'] ?? null)
            || ! preg_match('/\Akmj-user:[1-9][0-9]*\z/D', $claims['sub'])
            || ! is_int($claims['iat'] ?? null)
            || ! is_int($claims['nbf'] ?? null)
            || ! is_int($claims['exp'] ?? null)
            || $claims['iat'] > $now
            || $claims['nbf'] > $now
            || $claims['exp'] <= $now
            || ! is_string($claims['scope'] ?? null)) {
            return null;
        }

        try {
            $scopes = OAuthCore::parseScopes($claims['scope']);
        } catch (DomainException) {
            return null;
        }
        if (in_array('offline_access', $scopes, true)) {
            return null;
        }

        $claims['scopes'] = $scopes;

        return $claims;
    }

    private function decodeBase64Url(string $value): string
    {
        if ($value === '' || preg_match('/[^A-Za-z0-9_-]/', $value)) {
            throw new DomainException('OAUTH_TOKEN_INVALID');
        }
        $padded = strtr($value, '-_', '+/');
        $padded .= str_repeat('=', (4 - strlen($padded) % 4) % 4);
        $decoded = base64_decode($padded, true);
        if ($decoded === false) {
            throw new DomainException('OAUTH_TOKEN_INVALID');
        }

        return $decoded;
    }

    private function signingKey(): string
    {
        return OAuthCore::decodeSigningKey(config('codebridge_oauth.signing_key'));
    }

    /** @param array<string, ?string> $params */
    private function redirectWith(string $uri, array $params): string
    {
        $query = http_build_query(array_filter($params, fn ($v) => $v !== null), '', '&', PHP_QUERY_RFC3986);

        return $uri.(str_contains($uri, '?') ? '&' : '?').$query;
    }
}
