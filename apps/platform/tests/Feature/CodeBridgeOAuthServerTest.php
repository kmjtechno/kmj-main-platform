<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\CodeBridge\OAuth\OAuthCore;
use App\Services\CodeBridge\OAuth\OAuthServer;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class CodeBridgeOAuthServerTest extends TestCase
{
    use RefreshDatabase;

    private const RESOURCE = 'https://codebridge.example/mcp';

    private const REDIRECT = 'https://claude.ai/api/mcp/auth_callback';

    private string $verifier;

    protected function setUp(): void
    {
        parent::setUp();
        config([
            'codebridge_oauth.enabled' => true,
            'codebridge_oauth.issuer' => 'https://kmj.example',
            'codebridge_oauth.resource' => self::RESOURCE,
            'codebridge_oauth.signing_key' => base64_encode(str_repeat("\x07", SODIUM_CRYPTO_SIGN_SEEDBYTES)),
            'codebridge_oauth.kid' => 'test-kid',
        ]);
        $this->verifier = str_repeat('v', 64);
    }

    public function test_every_endpoint_is_dark_until_configured(): void
    {
        config(['codebridge_oauth.enabled' => false]);

        $this->get('/.well-known/oauth-authorization-server')->assertNotFound();
        $this->get('/oauth/jwks.json')->assertNotFound();
        $this->postJson('/oauth/register', ['redirect_uris' => [self::REDIRECT]])->assertNotFound();
        $this->post('/oauth/token', ['grant_type' => 'authorization_code'])->assertNotFound();

        config(['codebridge_oauth.enabled' => true, 'codebridge_oauth.signing_key' => null]);
        $this->get('/.well-known/oauth-authorization-server')->assertNotFound();
    }

    public function test_metadata_and_jwks_describe_a_pkce_public_client_server(): void
    {
        $this->get('/.well-known/oauth-authorization-server')
            ->assertOk()
            ->assertJson([
                'issuer' => 'https://kmj.example',
                'authorization_endpoint' => 'https://kmj.example/oauth/authorize',
                'token_endpoint' => 'https://kmj.example/oauth/token',
                'registration_endpoint' => 'https://kmj.example/oauth/register',
                'userinfo_endpoint' => 'https://kmj.example/oauth/userinfo',
                'code_challenge_methods_supported' => ['S256'],
                'token_endpoint_auth_methods_supported' => ['none'],
                'authorization_response_iss_parameter_supported' => true,
            ]);

        $jwks = $this->get('/oauth/jwks.json')->assertOk()->json('keys');
        $this->assertCount(1, $jwks);
        $this->assertSame(['kty' => 'OKP', 'crv' => 'Ed25519'], array_intersect_key($jwks[0], ['kty' => 1, 'crv' => 1]));
        $this->assertArrayNotHasKey('d', $jwks[0]);
    }

    public function test_registration_accepts_only_safe_public_clients(): void
    {
        $this->postJson('/oauth/register', [
            'client_name' => 'Claude',
            'redirect_uris' => [self::REDIRECT, 'http://localhost/callback'],
        ])->assertCreated()->assertJsonStructure(['client_id'])->assertJson(['token_endpoint_auth_method' => 'none']);

        foreach ([
            [],
            ['redirect_uris' => []],
            ['redirect_uris' => ['http://evil.example/cb']],
            ['redirect_uris' => ['https://a.example/cb#x']],
            ['redirect_uris' => [self::REDIRECT], 'token_endpoint_auth_method' => 'client_secret_basic'],
            ['redirect_uris' => [self::REDIRECT], 'grant_types' => ['client_credentials']],
        ] as $body) {
            $this->postJson('/oauth/register', $body)->assertStatus(400);
        }
    }

    public function test_full_authorization_code_flow_issues_a_resource_bound_token(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();

        $this->get('/oauth/authorize?'.$this->authorizeQuery($clientId))->assertRedirect('/login');

        $page = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId))
            ->assertOk()
            ->assertInertia(fn (Assert $p) => $p->component('auth/oauth-authorize')
                ->where('clientName', 'Claude')
                ->where('redirectHost', 'claude.ai')
                ->where('scopes', ['codebridge:read', 'codebridge:write']));
        $requestId = $page->viewData('page')['props']['requestId'];

        $redirect = $this->actingAs($user)->post('/oauth/authorize', ['request_id' => $requestId, 'decision' => 'approve'])
            ->assertRedirect()->headers->get('Location');
        $this->assertStringStartsWith(self::REDIRECT.'?', $redirect);
        parse_str((string) parse_url($redirect, PHP_URL_QUERY), $params);
        $this->assertSame('xyz', $params['state']);
        $this->assertSame('https://kmj.example', $params['iss']);

        $token = $this->post('/oauth/token', [
            'grant_type' => 'authorization_code',
            'code' => $params['code'],
            'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT,
            'code_verifier' => $this->verifier,
            'resource' => self::RESOURCE,
        ])->assertOk()->assertHeader('Cache-Control', 'no-store, private')->json();

        $claims = json_decode(base64_decode(strtr(explode('.', $token['access_token'])[1], '-_', '+/')), true);
        $this->assertSame(self::RESOURCE, $claims['aud']);
        $this->assertSame('https://kmj.example', $claims['iss']);
        $this->assertSame('kmj-user:'.$user->id, $claims['sub']);
        $this->assertSame('codebridge:read codebridge:write', $claims['scope']);
        $this->assertSame($claims['iat'] + 900, $claims['exp']);
        $this->assertSame('Bearer', $token['token_type']);

        $verified = app(OAuthServer::class)->verifyAccessToken($token['access_token']);
        $this->assertIsArray($verified);
        $this->assertSame('kmj-user:'.$user->id, $verified['sub']);
        $this->assertSame(['codebridge:read', 'codebridge:write'], $verified['scopes']);
        $this->assertNull(app(OAuthServer::class)->verifyAccessToken($token['access_token'].'x'));

        // The code is single use.
        $this->post('/oauth/token', [
            'grant_type' => 'authorization_code', 'code' => $params['code'], 'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT, 'code_verifier' => $this->verifier,
        ])->assertStatus(400)->assertJson(['error' => 'invalid_grant']);
    }

    public function test_userinfo_returns_verified_identity_for_openid_access_token(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $clientId = $this->registerClient();
        $page = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, [
            'scope' => 'openid codebridge:read',
        ]))->assertOk();
        $requestId = $page->viewData('page')['props']['requestId'];
        $location = $this->actingAs($user)->post('/oauth/authorize', [
            'request_id' => $requestId,
            'decision' => 'approve',
        ])->headers->get('Location');
        parse_str((string) parse_url((string) $location, PHP_URL_QUERY), $params);

        $token = $this->post('/oauth/token', [
            'grant_type' => 'authorization_code',
            'code' => $params['code'],
            'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT,
            'code_verifier' => $this->verifier,
            'resource' => self::RESOURCE,
        ])->assertOk()->json('access_token');

        $this->withToken($token)->getJson('/oauth/userinfo')
            ->assertOk()
            ->assertHeader('Cache-Control', 'no-store, private')
            ->assertJson([
                'sub' => 'kmj-user:'.$user->id,
                'email' => $user->email,
                'email_verified' => true,
                'name' => $user->name,
            ]);

        $this->getJson('/oauth/userinfo')
            ->assertUnauthorized()
            ->assertJson(['error' => 'invalid_token']);
    }

    public function test_wrong_verifier_redirect_or_client_cannot_redeem_a_code(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();
        $other = $this->registerClient();

        foreach ([
            ['code_verifier' => str_repeat('w', 64)],
            ['redirect_uri' => 'http://localhost/callback'],
            ['client_id' => $other],
        ] as $override) {
            $code = $this->approvedCode($user, $clientId);
            $this->post('/oauth/token', array_merge([
                'grant_type' => 'authorization_code', 'code' => $code, 'client_id' => $clientId,
                'redirect_uri' => self::REDIRECT, 'code_verifier' => $this->verifier,
            ], $override))->assertStatus(400)->assertJson(['error' => 'invalid_grant']);
        }
    }

    public function test_refresh_tokens_rotate_and_reuse_revokes_the_family(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();
        $first = $this->post('/oauth/token', [
            'grant_type' => 'authorization_code', 'code' => $this->approvedCode($user, $clientId),
            'client_id' => $clientId, 'redirect_uri' => self::REDIRECT, 'code_verifier' => $this->verifier,
        ])->assertOk()->json();

        $second = $this->post('/oauth/token', [
            'grant_type' => 'refresh_token', 'refresh_token' => $first['refresh_token'], 'client_id' => $clientId,
        ])->assertOk()->json();
        $this->assertNotSame($first['refresh_token'], $second['refresh_token']);

        $this->post('/oauth/token', [
            'grant_type' => 'refresh_token', 'refresh_token' => $first['refresh_token'], 'client_id' => $clientId,
        ])->assertStatus(400)->assertJson(['error' => 'invalid_grant']);

        $this->post('/oauth/token', [
            'grant_type' => 'refresh_token', 'refresh_token' => $second['refresh_token'], 'client_id' => $clientId,
        ])->assertStatus(400)->assertJson(['error' => 'invalid_grant']);
        $this->assertSame(0, DB::table('codebridge_oauth_refresh_tokens')->whereNull('revoked_at_epoch')->whereNull('rotated_at_epoch')->count());
    }

    public function test_invalid_client_or_redirect_is_shown_not_redirected(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();

        $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery('cb_unknown'))->assertStatus(400);
        $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, ['redirect_uri' => 'https://evil.example/cb']))->assertStatus(400);
    }

    public function test_protocol_errors_redirect_back_with_state(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();

        foreach ([
            [['resource' => 'https://other.example/mcp'], 'invalid_target'],
            [['code_challenge_method' => 'plain'], 'invalid_request'],
            [['scope' => 'admin'], 'invalid_scope'],
            [['response_type' => 'token'], 'unsupported_response_type'],
        ] as [$override, $error]) {
            $location = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, $override))
                ->assertRedirect()->headers->get('Location');
            $this->assertStringStartsWith(self::REDIRECT.'?', $location);
            $this->assertStringContainsString('error='.$error, $location);
            $this->assertStringContainsString('state=xyz', $location);
        }
    }

    public function test_denial_returns_access_denied(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();
        $page = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId))->assertOk();
        $requestId = $page->viewData('page')['props']['requestId'];

        $location = $this->actingAs($user)->post('/oauth/authorize', ['request_id' => $requestId, 'decision' => 'deny'])
            ->assertRedirect()->headers->get('Location');
        $this->assertStringContainsString('error=access_denied', $location);
        $this->assertSame(0, DB::table('codebridge_oauth_codes')->count());

        // A pending request can be decided only once.
        $this->actingAs($user)->post('/oauth/authorize', ['request_id' => $requestId, 'decision' => 'approve'])->assertStatus(400);
    }

    private function registerClient(): string
    {
        return $this->postJson('/oauth/register', [
            'client_name' => 'Claude',
            'redirect_uris' => [self::REDIRECT, 'http://localhost/callback'],
        ])->assertCreated()->json('client_id');
    }

    /** @param array<string, string> $override */
    private function authorizeQuery(string $clientId, array $override = []): string
    {
        return http_build_query(array_merge([
            'response_type' => 'code',
            'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT,
            'code_challenge' => OAuthCore::base64Url(hash('sha256', $this->verifier, true)),
            'code_challenge_method' => 'S256',
            'scope' => 'codebridge:read codebridge:write',
            'state' => 'xyz',
            'resource' => self::RESOURCE,
        ], $override));
    }

    private function approvedCode(User $user, string $clientId): string
    {
        $page = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId))->assertOk();
        $location = $this->actingAs($user)->post('/oauth/authorize', [
            'request_id' => $page->viewData('page')['props']['requestId'],
            'decision' => 'approve',
        ])->headers->get('Location');
        parse_str((string) parse_url((string) $location, PHP_URL_QUERY), $params);

        return $params['code'];
    }
}
