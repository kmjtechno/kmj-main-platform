<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\CodeBridge\OAuth\OAuthCore;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Real OAuth tokens against the real /user-access/introspect route: a user
 * only ever sees organizations they OWN with a live CodeBridge license, and
 * only devices with a live credential and a paired project.
 */
final class CodeBridgeUserAccessIntrospectionTest extends TestCase
{
    use RefreshDatabase;

    private const URL = '/api/codebridge/v1/user-access/introspect';

    private const RESOURCE = 'https://codebridge.example/mcp';

    private const REDIRECT = 'https://claude.ai/api/mcp/auth_callback';

    private string $verifier;

    protected function setUp(): void
    {
        parent::setUp();
        config([
            'codebridge.enabled' => true,
            'codebridge_oauth.enabled' => true,
            'codebridge_oauth.issuer' => 'https://kmj.example',
            'codebridge_oauth.resource' => self::RESOURCE,
            'codebridge_oauth.signing_key' => base64_encode(str_repeat("\x07", SODIUM_CRYPTO_SIGN_SEEDBYTES)),
            'codebridge_oauth.kid' => 'test-kid',
        ]);
        $this->verifier = str_repeat('v', 64);
    }

    public function test_owner_sees_only_own_live_tenant_devices_and_projects(): void
    {
        $user = User::factory()->create();
        $mine = $this->tenant($user, 'owner', 'my-device', 'my-project');
        $other = $this->tenant(User::factory()->create(), 'owner', 'foreign-device', 'foreign-project');

        $response = $this->withToken($this->accessToken($user))->postJson(self::URL)->assertOk()
            ->assertJson([
                'active' => true,
                'user_id' => 'kmj-user:'.$user->id,
                'memberships' => [[
                    'tenant_id' => $mine,
                    'permissions' => ['read', 'write'],
                    'devices' => ['my-device' => ['my-project']],
                ]],
            ]);
        self::assertStringNotContainsString($other, $response->getContent());
        self::assertStringNotContainsString('foreign', $response->getContent());
        self::assertStringContainsString('no-store', (string) $response->headers->get('Cache-Control'));
    }

    public function test_missing_malformed_and_tampered_tokens_are_rejected(): void
    {
        $user = User::factory()->create();
        $this->tenant($user, 'owner', 'my-device', 'my-project');
        $token = $this->accessToken($user);

        $this->postJson(self::URL)->assertUnauthorized()->assertJson(['active' => false]);
        $this->withToken('not.a.jwt')->postJson(self::URL)->assertUnauthorized();
        $this->withToken($token.'x')->postJson(self::URL)->assertUnauthorized();
        $this->withToken(str_repeat('a', 16385))->postJson(self::URL)->assertUnauthorized();
    }

    public function test_non_owner_member_gets_no_access(): void
    {
        $user = User::factory()->create();
        $this->tenant($user, 'member', 'my-device', 'my-project');

        $this->withToken($this->accessToken($user))->postJson(self::URL)
            ->assertForbidden()->assertJson(['active' => false]);
    }

    public function test_revoked_expired_or_inactive_license_removes_the_organization(): void
    {
        $user = User::factory()->create();
        $tenant = $this->tenant($user, 'owner', 'my-device', 'my-project');
        $token = $this->accessToken($user);
        $license = fn () => DB::table('kslp_licenses')->where('customer_id', $tenant);

        foreach ([
            ['status' => 'suspended'],
            ['status' => 'active', 'revoked_at' => now()],
            ['status' => 'active', 'revoked_at' => null, 'expires_at' => now()->subSecond()],
        ] as $bad) {
            $license()->update($bad);
            $this->withToken($token)->postJson(self::URL)->assertForbidden()->assertJson(['active' => false]);
        }

        $license()->update(['status' => 'active', 'revoked_at' => null, 'expires_at' => now()->addYear()]);
        $this->withToken($token)->postJson(self::URL)->assertOk();
    }

    public function test_revoked_or_expired_device_credential_and_unpaired_device_are_not_listed(): void
    {
        $user = User::factory()->create();
        $tenant = $this->tenant($user, 'owner', 'my-device', 'my-project');
        $token = $this->accessToken($user);
        $credential = fn () => DB::table('codebridge_device_credentials')->where('tenant_id', $tenant);

        $credential()->update(['revoked_at' => now()]);
        $this->withToken($token)->postJson(self::URL)->assertOk()
            ->assertJson(['memberships' => [['tenant_id' => $tenant, 'devices' => []]]])
            ->assertJsonPath('memberships.0.devices', []);

        $credential()->update(['revoked_at' => null, 'expires_at_epoch' => time() - 1]);
        $this->withToken($token)->postJson(self::URL)->assertOk()
            ->assertJson(['memberships' => [['devices' => []]]])
            ->assertJsonPath('memberships.0.devices', []);

        $credential()->update(['expires_at_epoch' => time() + 3600]);
        DB::table('codebridge_device_pairings')->where('tenant_id', $tenant)->delete();
        $this->withToken($token)->postJson(self::URL)->assertOk()
            ->assertJson(['memberships' => [['devices' => []]]])
            ->assertJsonPath('memberships.0.devices', []);
    }

    public function test_api_disabled_fails_closed(): void
    {
        $user = User::factory()->create();
        $token = $this->accessToken($user);
        config(['codebridge.enabled' => false]);
        $this->withToken($token)->postJson(self::URL)->assertStatus(503);
    }

    private function tenant(User $user, string $role, string $device, string $project): string
    {
        $tenant = (string) Str::uuid();
        $license = (string) Str::uuid();
        $activation = (string) Str::uuid();
        $now = now();
        DB::table('organizations')->insert(['id' => $tenant, 'name' => 'Org '.$device, 'created_at' => $now, 'updated_at' => $now]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(), 'organization_id' => $tenant, 'user_id' => $user->id,
            'role' => $role, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'professional', 'status' => 'active', 'sequence' => 1,
            'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
            'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('kslp_activations')->insert([
            'id' => $activation, 'license_id' => $license, 'server_identity' => 'codebridge-device:'.$device,
            'machine_identity_hash' => hash('sha256', $device), 'idempotency_key' => 'user-access:'.$device,
            'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::table('codebridge_device_credentials')->insert([
            'id' => (string) Str::uuid(), 'license_id' => $license, 'activation_id' => $activation,
            'tenant_id' => $tenant, 'device_id' => $device, 'server_identity' => 'codebridge-device:'.$device,
            'token_hash' => hash('sha256', 'user-access-token-'.$device), 'lease_sequence' => 0,
            'expires_at_epoch' => time() + 3600,
        ]);
        DB::table('codebridge_device_pairings')->insert([
            'id' => (string) Str::uuid(),
            'device_code_hash' => hash('sha256', 'device-code:'.$device),
            'user_code_hash' => hash('sha256', 'user-code:'.$device),
            'device_id' => $device, 'device_name' => $device, 'platform' => 'win32', 'arch' => 'x64',
            'project_id' => $project, 'project_name' => $project,
            'requested_permissions' => json_encode(['read']), 'code_challenge' => str_repeat('x', 43),
            'status' => 'consumed', 'tenant_id' => $tenant, 'license_id' => $license, 'activation_id' => $activation,
            'expires_at' => $now->copy()->addMinutes(5), 'consumed_at' => $now,
            'created_at' => $now, 'updated_at' => $now,
        ]);

        return $tenant;
    }

    /** Real PKCE authorization-code flow, as in CodeBridgeOAuthServerTest. */
    private function accessToken(User $user): string
    {
        $clientId = $this->postJson('/oauth/register', [
            'client_name' => 'Claude',
            'redirect_uris' => [self::REDIRECT, 'http://localhost/callback'],
        ])->assertCreated()->json('client_id');

        $query = http_build_query([
            'response_type' => 'code', 'client_id' => $clientId, 'redirect_uri' => self::REDIRECT,
            'code_challenge' => OAuthCore::base64Url(hash('sha256', $this->verifier, true)),
            'code_challenge_method' => 'S256', 'scope' => 'codebridge:read codebridge:write',
            'state' => 'xyz', 'resource' => self::RESOURCE,
        ]);
        $page = $this->actingAs($user)->get('/oauth/authorize?'.$query)->assertOk();
        $location = $this->actingAs($user)->post('/oauth/authorize', [
            'request_id' => $page->viewData('page')['props']['requestId'],
            'decision' => 'approve',
        ])->headers->get('Location');
        parse_str((string) parse_url((string) $location, PHP_URL_QUERY), $params);

        $token = $this->post('/oauth/token', [
            'grant_type' => 'authorization_code', 'code' => $params['code'], 'client_id' => $clientId,
            'redirect_uri' => self::REDIRECT, 'code_verifier' => $this->verifier, 'resource' => self::RESOURCE,
        ])->assertOk()->json('access_token');
        self::assertIsString($token);

        return $token;
    }
}
