<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer;
use App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal;
use App\Services\Licensing\OmniDesk\OmniDeskRenewalChallengeStore;
use App\Services\Licensing\OmniDeskDeviceRenewalProof;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Models\Organization;
use Tests\TestCase;

final class OmniDeskPrivateApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_private_status_fails_closed_when_authorizer_is_not_bound(): void
    {
        $fixture = $this->fixture();
        $this->app->forgetInstance(OmniDeskApiAuthorizer::class);

        $response = $this->getJson(
            '/api/v1/licensing/omnidesk/activations/'.$fixture['activation_id'].'/status',
        );

        $response
            ->assertStatus(503)
            ->assertExactJson(['error' => 'SERVER_UNAVAILABLE'])
            ->assertHeader('Cache-Control', 'no-store, private');
    }

    public function test_authorized_tenant_can_read_its_activation_status(): void
    {
        $fixture = $this->fixture();
        $this->bindPrincipal($fixture['organization_id']);

        $response = $this->getJson(
            '/api/v1/licensing/omnidesk/activations/'.$fixture['activation_id'].'/status',
        );

        $response
            ->assertOk()
            ->assertJsonPath('activation_id', $fixture['activation_id'])
            ->assertJsonPath('state', 'ACTIVE')
            ->assertJsonPath('current_sequence', 1)
            ->assertJsonPath('reason_codes', [])
            ->assertHeader('Cache-Control', 'no-store, private');
    }

    public function test_cross_tenant_activation_lookup_does_not_disclose_binding(): void
    {
        $fixture = $this->fixture();
        $other = Organization::query()->create(['name' => 'Other tenant']);
        $this->bindPrincipal((string) $other->getKey());

        $response = $this->getJson(
            '/api/v1/licensing/omnidesk/activations/'.$fixture['activation_id'].'/status',
        );

        $response
            ->assertStatus(404)
            ->assertExactJson(['error' => 'ACTIVATION_REVOKED'])
            ->assertHeader('Cache-Control', 'no-store, private');
    }

    public function test_current_entitlements_are_scoped_to_tenant_product_and_capability(): void
    {
        $fixture = $this->fixture();
        $other = Organization::query()->create(['name' => 'Other tenant']);
        Entitlement::query()->create([
            'organization_id' => $other->getKey(),
            'product_id' => $fixture['product_id'],
            'policy_id' => $fixture['policy_id'],
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
            'idempotency_key' => 'other-entitlement-'.Str::uuid(),
            'starts_at' => now()->subMinute(),
            'ends_at' => now()->addDay(),
        ]);
        Entitlement::query()->create([
            'organization_id' => $fixture['organization_id'],
            'product_id' => $fixture['product_id'],
            'policy_id' => $fixture['policy_id'],
            'capability' => 'unrelated.capability',
            'status' => 'active',
            'idempotency_key' => 'wrong-capability-'.Str::uuid(),
            'starts_at' => now()->subMinute(),
            'ends_at' => now()->addDay(),
        ]);
        $this->bindPrincipal($fixture['organization_id']);

        $response = $this->getJson('/api/v1/licensing/omnidesk/entitlements/current');

        $response
            ->assertOk()
            ->assertJsonPath('product_id', OmniDeskLicenseContract::PRODUCT_ID)
            ->assertJsonPath('product_slug', OmniDeskLicenseContract::PRODUCT_SLUG)
            ->assertJsonCount(1, 'entitlements')
            ->assertJsonPath('entitlements.0.entitlement_id', $fixture['entitlement_id'])
            ->assertHeader('Cache-Control', 'no-store, private');
    }

    public function test_non_manager_cannot_deactivate_activation(): void
    {
        $fixture = $this->fixture();
        $this->bindPrincipal($fixture['organization_id'], false);

        $response = $this->postJson(
            '/api/v1/licensing/omnidesk/activations/'.$fixture['activation_id'].'/deactivate',
            ['reason' => 'user requested device removal'],
        );

        $response
            ->assertStatus(403)
            ->assertExactJson(['error' => 'FORBIDDEN'])
            ->assertHeader('Cache-Control', 'no-store, private');
        $this->assertDatabaseHas('kslp_activations', [
            'id' => $fixture['activation_id'],
            'deactivated_at' => null,
        ]);
    }

    public function test_manager_deactivation_is_audited_and_idempotent(): void
    {
        $fixture = $this->fixture();
        $this->bindPrincipal($fixture['organization_id'], true);

        $url = '/api/v1/licensing/omnidesk/activations/'
            .$fixture['activation_id'].'/deactivate';

        $first = $this->postJson($url, ['reason' => 'replace retired workstation']);
        $first
            ->assertOk()
            ->assertJsonPath('activation_id', $fixture['activation_id'])
            ->assertJsonPath('state', 'REVOKED')
            ->assertJsonFragment(['ACTIVATION_REVOKED'])
            ->assertHeader('Cache-Control', 'no-store, private');

        $this->assertDatabaseMissing('kslp_activations', [
            'id' => $fixture['activation_id'],
            'deactivated_at' => null,
        ]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $fixture['license_id'],
            'actor_id' => 'test-user',
            'action' => 'omnidesk_activation_deactivated',
            'reason' => 'replace retired workstation',
        ]);

        $second = $this->postJson($url, ['reason' => 'repeat same request']);
        $second
            ->assertOk()
            ->assertJsonPath('state', 'REVOKED');

        self::assertSame(
            1,
            DB::table('kslp_license_events')
                ->where('license_id', $fixture['license_id'])
                ->where('action', 'omnidesk_activation_deactivated')
                ->count(),
        );
    }

    public function test_invalid_deactivation_reason_maps_to_deterministic_invalid_request(): void
    {
        $fixture = $this->fixture();
        $this->bindPrincipal($fixture['organization_id'], true);

        $response = $this->postJson(
            '/api/v1/licensing/omnidesk/activations/'.$fixture['activation_id'].'/deactivate',
            ['reason' => 'x'],
        );

        $response
            ->assertStatus(422)
            ->assertExactJson(['error' => 'INVALID_REQUEST'])
            ->assertHeader('Cache-Control', 'no-store, private');
    }

    public function test_renewal_server_challenge_is_hashed_and_consumed_only_once_with_device_signature(): void
    {
        [$f, $secret] = $this->renewalFixture();
        $store = app(OmniDeskRenewalChallengeStore::class);
        $issued = $store->issue($f['activation_id'], $f['organization_id']);

        self::assertSame(300, $issued['expires_in']);
        self::assertSame(43, strlen($issued['server_challenge']));
        $this->assertDatabaseHas('omnidesk_renewal_challenges', [
            'activation_id' => $f['activation_id'],
            'challenge_sha256' => hash('sha256', $issued['server_challenge']),
            'consumed_at' => null,
        ]);

        $proof = $this->signedRenewalRequest($f, $secret, $issued['server_challenge']);
        $store->verifyAndConsume($proof, $f['organization_id']);
        $used = DB::table('omnidesk_renewal_challenges')
            ->where('activation_id', $f['activation_id'])->first();
        self::assertNotNull($used->consumed_at);

        try {
            $store->verifyAndConsume($proof, $f['organization_id']);
            self::fail('A one-time renewal challenge cannot be consumed twice.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_REPLAY_DETECTED', $e->getMessage());
        }
    }

    public function test_renewal_challenge_cannot_be_claimed_by_another_tenant(): void
    {
        [$f, $secret] = $this->renewalFixture();
        $store = app(OmniDeskRenewalChallengeStore::class);
        $other = Organization::query()->create(['name' => 'Renewal attacker tenant']);
        $otherId = (string) $other->getKey();

        try {
            $store->issue($f['activation_id'], $otherId);
            self::fail('Foreign tenant issued challenge.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_RENEWAL_CHALLENGE_DENIED', $e->getMessage());
        }

        $issued = $store->issue($f['activation_id'], $f['organization_id']);
        try {
            $store->verifyAndConsume(
                $this->signedRenewalRequest($f, $secret, $issued['server_challenge']),
                $otherId,
            );
            self::fail('Foreign tenant consumed challenge.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_RENEWAL_CHALLENGE_DENIED', $e->getMessage());
        }

        $this->assertDatabaseHas('omnidesk_renewal_challenges', [
            'activation_id' => $f['activation_id'],
            'consumed_at' => null,
        ]);
    }

    public function test_invalid_signature_does_not_consume_renewal_challenge(): void
    {
        [$f, $secret] = $this->renewalFixture();
        $store = app(OmniDeskRenewalChallengeStore::class);
        $issued = $store->issue($f['activation_id'], $f['organization_id']);
        $proof = $this->signedRenewalRequest($f, $secret, $issued['server_challenge']);
        $proof['client_nonce'] = 'nonce-wrong-0123456789abcdef';

        try {
            $store->verifyAndConsume($proof, $f['organization_id']);
            self::fail('Tampered signed request was accepted.');
        } catch (DomainException $e) {
            self::assertSame('FORBIDDEN', $e->getMessage());
        }

        $this->assertDatabaseHas('omnidesk_renewal_challenges', [
            'activation_id' => $f['activation_id'],
            'consumed_at' => null,
        ]);
    }

    public function test_expired_server_challenge_and_stale_cursor_fail_closed(): void
    {
        [$f, $secret] = $this->renewalFixture();
        $store = app(OmniDeskRenewalChallengeStore::class);
        $issued = $store->issue($f['activation_id'], $f['organization_id']);
        $proof = $this->signedRenewalRequest($f, $secret, $issued['server_challenge']);

        $stale = $proof;
        $stale['current_sequence'] = 2;
        try {
            $store->verifyAndConsume($stale, $f['organization_id']);
            self::fail('Stale lease cursor accepted.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_REPLAY_DETECTED', $e->getMessage());
        }

        DB::table('omnidesk_renewal_challenges')
            ->where('activation_id', $f['activation_id'])
            ->update(['expires_at' => now()->subSecond()]);
        try {
            $store->verifyAndConsume($proof, $f['organization_id']);
            self::fail('Expired renewal challenge accepted.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_RENEWAL_CHALLENGE_EXPIRED', $e->getMessage());
        }
    }

    public function test_issuing_new_challenge_invalidates_old_one_and_revocation_blocks_new_issue(): void
    {
        [$f, $secret] = $this->renewalFixture();
        $store = app(OmniDeskRenewalChallengeStore::class);
        $old = $store->issue($f['activation_id'], $f['organization_id']);
        $fresh = $store->issue($f['activation_id'], $f['organization_id']);
        self::assertNotSame($old['server_challenge'], $fresh['server_challenge']);
        $this->assertDatabaseCount('omnidesk_renewal_challenges', 1);

        try {
            $store->verifyAndConsume(
                $this->signedRenewalRequest($f, $secret, $old['server_challenge']),
                $f['organization_id'],
            );
            self::fail('Prior server challenge was not rotated away.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_REPLAY_DETECTED', $e->getMessage());
        }

        DB::table('kslp_licenses')->where('id', $f['license_id'])
            ->update(['status' => 'revoked', 'revoked_at' => now()]);
        try {
            $store->issue($f['activation_id'], $f['organization_id']);
            self::fail('Revoked license issued renewal challenge.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_RENEWAL_CHALLENGE_DENIED', $e->getMessage());
        }
    }

    /**
     * @return array{array<string, string>, non-empty-string}
     */
    private function renewalFixture(): array
    {
        $f = $this->fixture();
        $pair = sodium_crypto_sign_seed_keypair(hash('sha256', 'omnidesk-renewal-test-only', true));
        $public = sodium_crypto_sign_publickey($pair);
        $secret = sodium_crypto_sign_secretkey($pair);
        DB::table('omnidesk_activation_bindings')
            ->where('activation_id', $f['activation_id'])
            ->update([
                'device_public_key' => rtrim(strtr(base64_encode($public), '+/', '-_'), '='),
                'device_public_key_fingerprint' => 'sha256:'.hash('sha256', $public),
            ]);

        return [$f, $secret];
    }

    /**
     * @param  array<string, string>  $fixture
     * @return array<string, mixed>
     */
    private function signedRenewalRequest(array $fixture, string $secret, string $challenge): array
    {
        $request = [
            'activation_id' => $fixture['activation_id'],
            'current_jti' => 'jti-private-api-test',
            'current_sequence' => 1,
            'server_challenge' => $challenge,
            'client_nonce' => 'nonce-0123456789abcdef',
            'client_version' => '0.0.1',
            'proof_scheme' => 'KMJ-OMNIDESK-RENEW-v1',
            'device_signature' => 'unsigned',
        ];
        $message = app(OmniDeskDeviceRenewalProof::class)->canonicalMessage($request);
        $signature = sodium_crypto_sign_detached($message, $secret);
        $request['device_signature'] = rtrim(strtr(base64_encode($signature), '+/', '-_'), '=');

        return $request;
    }

    private function bindPrincipal(string $organizationId, bool $canManage = true): void
    {
        $this->app->instance(
            OmniDeskApiAuthorizer::class,
            new class($organizationId, $canManage) implements OmniDeskApiAuthorizer
            {
                public function __construct(
                    private readonly string $organizationId,
                    private readonly bool $canManage,
                ) {}

                public function authorize(Request $request): OmniDeskApiPrincipal
                {
                    unset($request);

                    return new OmniDeskApiPrincipal(
                        actorId: 'test-user',
                        organizationId: $this->organizationId,
                        canManage: $this->canManage,
                    );
                }
            },
        );
    }

    /**
     * @return array{
     *   activation_id:string,
     *   license_id:string,
     *   entitlement_id:string,
     *   organization_id:string,
     *   product_id:string,
     *   policy_id:string
     * }
     */
    private function fixture(): array
    {
        $organization = Organization::query()->create(['name' => 'OmniDesk tenant']);
        $product = Product::query()->create([
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'name' => 'KMJ OmniDesk',
            'status' => 'active',
            'lifecycle' => 'pre-alpha',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => true,
        ]);
        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'omnidesk.private.api.test',
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
        ]);
        $entitlement = Entitlement::query()->create([
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'policy_id' => $policy->getKey(),
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
            'idempotency_key' => 'omnidesk-private-api-'.Str::uuid(),
            'starts_at' => now()->subMinute(),
            'ends_at' => now()->addDays(30),
        ]);

        $licenseId = (string) Str::uuid();
        DB::table('kslp_licenses')->insert([
            'id' => $licenseId,
            'customer_id' => $organization->getKey(),
            'product' => OmniDeskLicenseContract::PRODUCT_ID,
            'plan' => 'professional',
            'status' => 'active',
            'trial_subject_hash' => null,
            'sequence' => 1,
            'starts_at' => now()->subDay(),
            'expires_at' => now()->addDays(30),
            'grace_until' => now()->addDays(37),
            'revoked_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $activationId = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $activationId,
            'license_id' => $licenseId,
            'server_identity' => 'omnidesk-private-api-device',
            'machine_identity_hash' => hash('sha256', 'omnidesk-private-api-machine'),
            'idempotency_key' => 'generic-private-api-'.Str::uuid(),
            'activated_at' => now(),
            'deactivated_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        DB::table('omnidesk_activation_bindings')->insert([
            'activation_id' => $activationId,
            'entitlement_id' => $entitlement->getKey(),
            'organization_id' => $organization->getKey(),
            'device_public_key' => rtrim(strtr(base64_encode(str_repeat('k', 32)), '+/', '-_'), '='),
            'device_public_key_fingerprint' => 'sha256:'.hash('sha256', str_repeat('k', 32)),
            'installation_id' => 'install-private-api-test',
            'idempotency_key' => 'omnidesk-private-binding-'.Str::uuid(),
            'current_jti' => 'jti-private-api-test',
            'current_sequence' => 1,
            'current_nonce' => 'nonce-private-api-0000000000000000001',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return [
            'activation_id' => $activationId,
            'license_id' => $licenseId,
            'entitlement_id' => (string) $entitlement->getKey(),
            'organization_id' => (string) $organization->getKey(),
            'product_id' => (string) $product->getKey(),
            'policy_id' => (string) $policy->getKey(),
        ];
    }
}
