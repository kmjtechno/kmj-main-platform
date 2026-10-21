<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\Licensing\OmniDesk\OmniDeskActivationBindingStore;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Models\Organization;
use Tests\TestCase;

final class OmniDeskActivationBindingStoreTest extends TestCase
{
    use RefreshDatabase;

    public function test_binding_is_tenant_product_and_device_bound_and_idempotent(): void
    {
        $fixture = $this->fixture();
        $store = app(OmniDeskActivationBindingStore::class);

        $first = $store->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );
        $second = $store->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );

        self::assertSame($first['activation_id'], $second['activation_id']);
        $this->assertDatabaseCount('omnidesk_activation_bindings', 1);
        $this->assertDatabaseHas('omnidesk_activation_bindings', [
            'activation_id' => $fixture['activation_id'],
            'entitlement_id' => $fixture['entitlement_id'],
            'organization_id' => $fixture['organization_id'],
            'device_public_key_fingerprint' => $fixture['device_fingerprint'],
            'installation_id' => $fixture['installation_id'],
            'current_sequence' => 0,
        ]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $fixture['license_id'],
            'action' => 'omnidesk_device_bound',
            'actor_id' => 'test-actor',
        ]);
    }

    public function test_idempotency_key_cannot_rebind_a_different_installation(): void
    {
        $fixture = $this->fixture();
        $store = app(OmniDeskActivationBindingStore::class);
        $store->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ACTIVATION_CONFLICT');

        $store->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            'install-different-0002',
            $fixture['binding_idempotency_key'],
            'test-actor',
        );
    }

    public function test_cross_tenant_license_binding_fails_closed(): void
    {
        $fixture = $this->fixture();
        $other = Organization::query()->create(['name' => 'Other Tenant']);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_PRODUCT_OR_TENANT_MISMATCH');

        app(OmniDeskActivationBindingStore::class)->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            (string) $other->getKey(),
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );
    }

    public function test_device_fingerprint_must_match_the_ed25519_public_key(): void
    {
        $fixture = $this->fixture();

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_DEVICE_BINDING_INVALID');

        app(OmniDeskActivationBindingStore::class)->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            'sha256:'.str_repeat('0', 64),
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );
    }

    public function test_lease_cursor_advances_once_and_replay_is_rejected(): void
    {
        $fixture = $this->fixture();
        $store = app(OmniDeskActivationBindingStore::class);
        $store->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );

        $first = $store->advanceLease(
            $fixture['activation_id'],
            null,
            0,
            'jti-0000000000000001',
            1,
        );
        self::assertSame(1, (int) $first['current_sequence']);
        self::assertSame('jti-0000000000000001', $first['current_jti']);

        try {
            $store->advanceLease(
                $fixture['activation_id'],
                null,
                0,
                'jti-replay-0000000002',
                1,
            );
            self::fail('Replayed lease cursor must fail closed.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_REPLAY_DETECTED', $exception->getMessage());
        }

        $second = $store->advanceLease(
            $fixture['activation_id'],
            'jti-0000000000000001',
            1,
            'jti-0000000000000002',
            2,
        );
        self::assertSame(2, (int) $second['current_sequence']);
    }

    public function test_deactivated_activation_cannot_be_bound(): void
    {
        $fixture = $this->fixture();
        DB::table('kslp_activations')
            ->where('id', $fixture['activation_id'])
            ->update(['deactivated_at' => now()]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ACTIVATION_CONFLICT');

        app(OmniDeskActivationBindingStore::class)->bind(
            $fixture['activation_id'],
            $fixture['license_id'],
            $fixture['entitlement_id'],
            $fixture['organization_id'],
            $fixture['device_public_key'],
            $fixture['device_fingerprint'],
            $fixture['installation_id'],
            $fixture['binding_idempotency_key'],
            'test-actor',
        );
    }

    /**
     * @return array{
     *   activation_id:string,
     *   license_id:string,
     *   entitlement_id:string,
     *   organization_id:string,
     *   device_public_key:string,
     *   device_fingerprint:string,
     *   installation_id:string,
     *   binding_idempotency_key:string
     * }
     */
    private function fixture(): array
    {
        $organization = Organization::query()->create(['name' => 'OmniDesk Tenant']);
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
            'code' => 'omnidesk.remote.access.test',
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
        ]);
        $entitlement = Entitlement::query()->create([
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'policy_id' => $policy->getKey(),
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
            'idempotency_key' => 'omnidesk-entitlement-test-'.Str::uuid(),
            'starts_at' => now()->subMinute(),
            'ends_at' => now()->addDay(),
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
            'starts_at' => now()->subMinute(),
            'expires_at' => now()->addDay(),
            'grace_until' => now()->addDays(2),
            'revoked_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $activationId = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $activationId,
            'license_id' => $licenseId,
            'server_identity' => 'omnidesk-test-device',
            'machine_identity_hash' => hash('sha256', 'omnidesk-test-machine'),
            'idempotency_key' => 'generic-activation-'.Str::uuid(),
            'activated_at' => now(),
            'deactivated_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $pair = sodium_crypto_sign_keypair();
        $publicKey = sodium_crypto_sign_publickey($pair);
        $encoded = rtrim(strtr(base64_encode($publicKey), '+/', '-_'), '=');

        return [
            'activation_id' => $activationId,
            'license_id' => $licenseId,
            'entitlement_id' => (string) $entitlement->getKey(),
            'organization_id' => (string) $organization->getKey(),
            'device_public_key' => $encoded,
            'device_fingerprint' => 'sha256:'.hash('sha256', $publicKey),
            'installation_id' => 'install-omnidesk-test-0001',
            'binding_idempotency_key' => 'omnidesk-binding-test-0001',
        ];
    }
}
