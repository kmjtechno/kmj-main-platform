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

    private const STATIC_CLIENT = 'kmj_codebridge_claude';

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
            'codebridge_oauth.static_clients' => [
                self::STATIC_CLIENT => [
                    'client_name' => 'Claude',
                    'redirect_uris' => [self::REDIRECT],
                ],
            ],
        ]);
        $this->verifier = str_repeat('v', 64);
    }

    public function test_every_endpoint_is_dark_until_configured(): void
    {
        config(['codebridge_oauth.enabled' => false]);

        $this->get('/.well-known/oauth-authorization-server')->assertNotFound();
        $this->get('/.well-known/openid-configuration')->assertNotFound();
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
                'subject_types_supported' => ['public'],
                'id_token_signing_alg_values_supported' => ['EdDSA'],
            ]);

        $this->get('/.well-known/openid-configuration')
            ->assertOk()
            ->assertJson([
                'issuer' => 'https://kmj.example',
                'userinfo_endpoint' => 'https://kmj.example/oauth/userinfo',
                'id_token_signing_alg_values_supported' => ['EdDSA'],
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

    public function test_static_public_client_rehydrates_and_completes_pkce_flow(): void
    {
        $user = User::factory()->create();

        $first = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery(self::STATIC_CLIENT))
            ->assertOk();
        $this->assertSame(1, DB::table('codebridge_oauth_clients')->where('client_id', self::STATIC_CLIENT)->count());

        DB::table('codebridge_oauth_clients')->where('client_id', self::STATIC_CLIENT)->delete();
        $this->assertSame(0, DB::table('codebridge_oauth_clients')->where('client_id', self::STATIC_CLIENT)->count());

        $page = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery(self::STATIC_CLIENT))
            ->assertOk()
            ->assertInertia(fn (Assert $p) => $p->component('auth/oauth-authorize')
                ->where('clientName', 'Claude')
                ->where('redirectHost', 'claude.ai'));
        $this->assertSame(1, DB::table('codebridge_oauth_clients')->where('client_id', self::STATIC_CLIENT)->count());

        $location = $this->actingAs($user)->post('/oauth/authorize', [
            'request_id' => $page->viewData('page')['props']['requestId'],
            'decision' => 'approve',
        ])->assertRedirect()->headers->get('Location');
        parse_str((string) parse_url((string) $location, PHP_URL_QUERY), $params);

        $this->post('/oauth/token', [
            'grant_type' => 'authorization_code',
            'code' => $params['code'],
            'client_id' => self::STATIC_CLIENT,
            'redirect_uri' => self::REDIRECT,
            'code_verifier' => $this->verifier,
            'resource' => self::RESOURCE,
        ])->assertOk()->assertJson(['token_type' => 'Bearer']);

        $this->assertNotNull($first->viewData('page')['props']['requestId']);
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
        $this->assertArrayNotHasKey('id_token', $token);

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

    public function test_a_different_ai_app_email_does_not_bind_the_kmj_oauth_identity(): void
    {
        $kmjAccount = User::factory()->create([
            'email' => 'authorized-kmj-user@example.test',
            'email_verified_at' => now(),
        ]);

        foreach ([
            ['Claude', self::REDIRECT],
            ['ChatGPT', 'https://chatgpt.com/connector_platform_oauth_redirect'],
            ['Gemini', 'https://oauth-redirect.googleusercontent.com/r/user_bound_custom-mcp-test'],
        ] as [$clientName, $redirectUri]) {
            $clientId = $this->postJson('/oauth/register', [
                'client_name' => $clientName,
                'redirect_uris' => [$redirectUri],
            ])->assertCreated()->json('client_id');

            // There is intentionally no AI-provider email in the OAuth
            // request. The account chosen here belongs to KMJ Platform.
            $query = $this->authorizeQuery($clientId, [
                'redirect_uri' => $redirectUri,
            ]);
            $page = $this->actingAs($kmjAccount)->get('/oauth/authorize?'.$query)->assertOk();
            $this->assertSame($clientName, $page->viewData('page')['props']['clientName']);
            $this->assertSame('authorized-kmj-user@example.test', $page->viewData('page')['props']['account']['email']);

            $requestId = $page->viewData('page')['props']['requestId'];
            $callback = $this->actingAs($kmjAccount)->post('/oauth/authorize', [
                'request_id' => $requestId,
                'decision' => 'approve',
            ])->assertRedirect()->headers->get('Location');

            parse_str((string) parse_url((string) $callback, PHP_URL_QUERY), $parameters);
            $tokens = $this->post('/oauth/token', [
                'grant_type' => 'authorization_code',
                'code' => $parameters['code'],
                'client_id' => $clientId,
                'redirect_uri' => $redirectUri,
                'code_verifier' => $this->verifier,
                'resource' => self::RESOURCE,
            ])->assertOk()->json();

            $claims = app(OAuthServer::class)->verifyAccessToken($tokens['access_token']);
            $this->assertSame('kmj-user:'.$kmjAccount->id, $claims['sub']);
            $this->assertSame(self::RESOURCE, $claims['aud']);
            $this->assertSame($clientId, $claims['client_id']);
            $this->assertArrayNotHasKey('email', $claims);
        }
    }

    public function test_account_switch_preserves_validated_pkce_and_consumes_old_consent(): void
    {
        $wrong = User::factory()->create(['email' => 'wrong-kmj@example.test']);
        $authorized = User::factory()->create(['email' => 'owner-kmj@example.test']);
        $clientId = $this->registerClient();
        $state = 'client-generated-opaque-state-123';
        $query = $this->authorizeQuery($clientId, ['state' => $state]);

        $old = $this->actingAs($wrong)->get('/oauth/authorize?'.$query)->assertOk();
        $this->assertSame('wrong-kmj@example.test', $old->viewData('page')['props']['account']['email']);
        $oldRequestId = $old->viewData('page')['props']['requestId'];

        $switched = $this->actingAs($wrong)->post('/oauth/authorize', [
            'request_id' => $oldRequestId,
            'decision' => 'switch',
        ])->assertRedirect();
        $this->assertGuest();
        $this->assertDatabaseCount('codebridge_oauth_codes', 0);
        $location = (string) $switched->headers->get('Location');
        $this->assertSame('/oauth/authorize', parse_url($location, PHP_URL_PATH));
        parse_str((string) parse_url($location, PHP_URL_QUERY), $restored);
        $this->assertSame($clientId, $restored['client_id']);
        $this->assertSame(self::REDIRECT, $restored['redirect_uri']);
        $this->assertSame($state, $restored['state']);
        $this->assertSame(OAuthCore::base64Url(hash('sha256', $this->verifier, true)), $restored['code_challenge']);
        $this->assertSame(self::RESOURCE, $restored['resource']);

        $this->get($location)->assertRedirect('/login');

        // A consumed consent cannot be replayed after switching accounts.
        $this->actingAs($authorized)->post('/oauth/authorize', [
            'request_id' => $oldRequestId,
            'decision' => 'approve',
        ])->assertBadRequest();
        $this->assertDatabaseCount('codebridge_oauth_codes', 0);

        $new = $this->actingAs($authorized)->get($location)->assertOk();
        $this->assertSame('owner-kmj@example.test', $new->viewData('page')['props']['account']['email']);
        $callback = $this->actingAs($authorized)->post('/oauth/authorize', [
            'request_id' => $new->viewData('page')['props']['requestId'],
            'decision' => 'approve',
        ])->assertRedirect()->headers->get('Location');
        parse_str((string) parse_url((string) $callback, PHP_URL_QUERY), $params);

        $access = $this->post('/oauth/token', [
            'grant_type' => 'authorization_code',
            'code' => $params['code'],
            'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT,
            'code_verifier' => $this->verifier,
            'resource' => self::RESOURCE,
        ])->assertOk()->json('access_token');

        $this->assertSame(
            'kmj-user:'.$authorized->id,
            app(OAuthServer::class)->verifyAccessToken($access)['sub'],
        );
        $this->assertSame(1, DB::table('codebridge_oauth_codes')->count());
    }

    public function test_consent_cannot_be_approved_after_account_changes_in_another_tab(): void
    {
        $first = User::factory()->create(['email' => 'first@example.test']);
        $second = User::factory()->create(['email' => 'second@example.test']);
        $clientId = $this->registerClient();
        $page = $this->actingAs($first)->get('/oauth/authorize?'.$this->authorizeQuery($clientId))->assertOk();
        $this->assertSame('first@example.test', $page->viewData('page')['props']['account']['email']);
        $requestId = $page->viewData('page')['props']['requestId'];

        $this->actingAs($second)->post('/oauth/authorize', [
            'request_id' => $requestId,
            'decision' => 'approve',
        ])->assertForbidden();
        $this->assertDatabaseCount('codebridge_oauth_codes', 0);
        $this->actingAs($second)->post('/oauth/authorize', [
            'request_id' => $requestId,
            'decision' => 'switch',
        ])->assertBadRequest();
        $this->assertDatabaseCount('codebridge_oauth_codes', 0);
    }

    public function test_switch_rejects_unvalidated_or_replayed_request_ids(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();
        $this->actingAs($user)->post('/oauth/authorize', [
            'request_id' => str_repeat('a', 40),
            'decision' => 'switch',
        ])->assertBadRequest();
        $this->assertAuthenticatedAs($user);

        $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, [
            'redirect_uri' => 'https://evil.example/callback',
        ]))->assertBadRequest();
        $this->assertDatabaseCount('codebridge_oauth_codes', 0);
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

        $tokens = $this->post('/oauth/token', [
            'grant_type' => 'authorization_code',
            'code' => $params['code'],
            'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT,
            'code_verifier' => $this->verifier,
            'resource' => self::RESOURCE,
        ])->assertOk()->json();

        $this->assertArrayHasKey('id_token', $tokens);
        $idParts = explode('.', $tokens['id_token']);
        $this->assertCount(3, $idParts);
        $idHeader = json_decode(base64_decode(strtr($idParts[0], '-_', '+/')), true);
        $idClaims = json_decode(base64_decode(strtr($idParts[1], '-_', '+/')), true);
        $this->assertSame('JWT', $idHeader['typ']);
        $this->assertSame('EdDSA', $idHeader['alg']);
        $this->assertSame('https://kmj.example', $idClaims['iss']);
        $this->assertSame($clientId, $idClaims['aud']);
        $this->assertSame('kmj-user:'.$user->id, $idClaims['sub']);
        $this->assertSame($user->email, $idClaims['email']);
        $this->assertTrue($idClaims['email_verified']);
        $this->assertSame($user->name, $idClaims['name']);

        $token = $tokens['access_token'];
        $this->withToken($token)->getJson('/oauth/userinfo')
            ->assertOk()
            ->assertHeader('Cache-Control', 'no-store, private')
            ->assertJson([
                'sub' => 'kmj-user:'.$user->id,
                'email' => $user->email,
                'email_verified' => true,
                'name' => $user->name,
            ]);

        $this->withHeader('Authorization', '')->getJson('/oauth/userinfo')
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

    public function test_gemini_spark_opaque_state_round_trips_without_truncation(): void
    {
        $redirect = 'https://oauth-redirect.googleusercontent.com/r/user_bound_custom-mcp-123-kmjtechno_com';
        $clientId = $this->postJson('/oauth/register', [
            'client_name' => 'Gemini Spark',
            'redirect_uris' => [$redirect],
        ])->assertCreated()->json('client_id');
        $state = str_repeat('opaque+/=%._-AZ09', 90).'tail-%&+';
        $this->assertGreaterThan(512, strlen($state));

        $user = User::factory()->create();
        foreach (['approve', 'deny'] as $decision) {
            $page = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, [
                'redirect_uri' => $redirect,
                'state' => $state,
            ]))->assertOk();

            $location = $this->actingAs($user)->post('/oauth/authorize', [
                'request_id' => $page->viewData('page')['props']['requestId'],
                'decision' => $decision,
            ])->assertRedirect()->headers->get('Location');

            $this->assertStringStartsWith($redirect.'?', $location);
            parse_str((string) parse_url($location, PHP_URL_QUERY), $params);
            $this->assertSame($state, $params['state']);
            $this->assertSame('https://kmj.example', $params['iss']);
            if ($decision === 'approve') {
                $this->assertArrayHasKey('code', $params);
            } else {
                $this->assertSame('access_denied', $params['error']);
            }
        }

        // Error callbacks must preserve the same opaque state value.
        $errorLocation = $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, [
            'redirect_uri' => $redirect,
            'state' => $state,
            'resource' => 'https://wrong.example/mcp',
        ]))->assertRedirect()->headers->get('Location');
        parse_str((string) parse_url($errorLocation, PHP_URL_QUERY), $errorParams);
        $this->assertSame($state, $errorParams['state']);
        $this->assertSame('invalid_target', $errorParams['error']);
    }

    public function test_oversized_oauth_state_is_rejected_without_redirect_or_truncation(): void
    {
        $user = User::factory()->create();
        $clientId = $this->registerClient();
        $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, [
            'state' => str_repeat('s', 4096),
        ]))->assertOk();

        $this->actingAs($user)->get('/oauth/authorize?'.$this->authorizeQuery($clientId, [
            'state' => str_repeat('s', 4097),
        ]))->assertStatus(400)->assertSee('invalid_request');
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
