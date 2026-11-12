<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\OmniDesk\OmniDeskActivationBindingStore;
use App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer;
use App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal;
use App\Services\Licensing\OmniDesk\OmniDeskMembershipApiAuthorizer;
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
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use Tests\TestCase;

/**
 * Adversarial coverage for the caller-supplied seat limit and the membership
 * authorizer. No plan limit is assumed anywhere: every limit below is a test
 * input, never a product default. True concurrent-seat races need a real
 * PostgreSQL connection and are NOT proven here (SQLite serializes writers);
 * the count runs under the license row lock to make them serialize in prod.
 */
final class OmniDeskSeatAndAuthorizerTest extends TestCase
{
    use RefreshDatabase;

    public function test_seat_limit_blocks_the_next_device_but_not_an_idempotent_retry(): void
    {
        $f = $this->tenant();
        $first = $this->device($f, 'one');
        $second = $this->device($f, 'two');

        $this->bind($f, $first, 1);
        // Retry of the already-bound device must not need a free seat.
        $this->bind($f, $first, 1);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_DEVICE_LIMIT_REACHED');
        $this->bind($f, $second, 1);
    }

    public function test_denied_seat_leaves_no_binding_row(): void
    {
        $f = $this->tenant();
        $this->bind($f, $this->device($f, 'one'), 1);
        $second = $this->device($f, 'two');

        try {
            $this->bind($f, $second, 1);
            self::fail('second device must be refused');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_DEVICE_LIMIT_REACHED', $e->getMessage());
        }

        $this->assertDatabaseCount('omnidesk_activation_bindings', 1);
        $this->assertDatabaseMissing('omnidesk_activation_bindings', ['activation_id' => $second['activation_id']]);
    }

    public function test_revoked_device_frees_its_seat(): void
    {
        $f = $this->tenant();
        $first = $this->device($f, 'one');
        $second = $this->device($f, 'two');
        $this->bind($f, $first, 1);

        DB::table('kslp_activations')->where('id', $first['activation_id'])->update(['deactivated_at' => now()]);

        $row = $this->bind($f, $second, 1);
        self::assertSame($second['activation_id'], $row['activation_id']);
    }

    public function test_revoked_device_cannot_be_rebound(): void
    {
        $f = $this->tenant();
        $first = $this->device($f, 'one');
        DB::table('kslp_activations')->where('id', $first['activation_id'])->update(['deactivated_at' => now()]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_ACTIVATION_CONFLICT');
        $this->bind($f, $first, 5);
    }

    public function test_no_limit_means_no_seat_check_and_zero_is_rejected(): void
    {
        $f = $this->tenant();
        $this->bind($f, $this->device($f, 'one'), null);
        $this->bind($f, $this->device($f, 'two'), null);
        $this->assertDatabaseCount('omnidesk_activation_bindings', 2);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_DEVICE_LIMIT_INVALID');
        $this->bind($f, $this->device($f, 'three'), 0);
    }

    public function test_seats_are_counted_per_license_not_across_tenants(): void
    {
        $a = $this->tenant();
        $b = $this->tenant();
        $this->bind($a, $this->device($a, 'one'), 1);

        $row = $this->bind($b, $this->device($b, 'one'), 1);
        self::assertSame($b['organization_id'], $row['organization_id']);
    }

    public function test_reused_nonce_and_stale_sequence_are_rejected(): void
    {
        $f = $this->tenant();
        $d = $this->device($f, 'one');
        $this->bind($f, $d, 1);
        $store = app(OmniDeskActivationBindingStore::class);
        $n1 = str_repeat('a', 43);
        $n2 = str_repeat('b', 43);

        $store->advanceLease($d['activation_id'], null, 0, null, 'jti-1', 1, $n1);
        $store->advanceLease($d['activation_id'], 'jti-1', 1, $n1, 'jti-2', 2, $n2);

        foreach ([[null, 0, null, 'jti-1b', 1, $n1], ['jti-1', 1, $n1, 'jti-2b', 2, $n2]] as $args) {
            try {
                $store->advanceLease($d['activation_id'], ...$args);
                self::fail('replayed cursor must be rejected');
            } catch (DomainException $e) {
                self::assertSame('OMNIDESK_REPLAY_DETECTED', $e->getMessage());
            }
        }
        $this->assertDatabaseHas('omnidesk_activation_bindings', [
            'activation_id' => $d['activation_id'], 'current_sequence' => 2, 'current_jti' => 'jti-2',
        ]);
    }

    public function test_authorizer_denies_anonymous_callers(): void
    {
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_UNAUTHENTICATED');
        $this->authorize(null, (string) Str::uuid());
    }

    public function test_authorizer_denies_missing_or_malformed_tenant_header(): void
    {
        $user = User::factory()->create();
        foreach ([null, '', 'not-a-uuid', "' OR 1=1 --"] as $header) {
            try {
                $this->authorize($user, $header);
                self::fail('tenant header must be explicit and well formed');
            } catch (DomainException $e) {
                self::assertSame('OMNIDESK_FORBIDDEN', $e->getMessage());
            }
        }
    }

    public function test_authorizer_denies_cross_tenant_non_members(): void
    {
        $user = User::factory()->create();
        $mine = Organization::query()->create(['name' => 'Mine']);
        $other = Organization::query()->create(['name' => 'Other']);
        OrganizationMembership::query()->create([
            'organization_id' => $mine->getKey(), 'user_id' => $user->getKey(), 'role' => 'owner',
        ]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_FORBIDDEN');
        $this->authorize($user, (string) $other->getKey());
    }

    public function test_authorizer_grants_manage_only_to_owners(): void
    {
        $owner = User::factory()->create();
        $member = User::factory()->create();
        $org = Organization::query()->create(['name' => 'Tenant']);
        OrganizationMembership::query()->create([
            'organization_id' => $org->getKey(), 'user_id' => $owner->getKey(), 'role' => 'owner',
        ]);
        OrganizationMembership::query()->create([
            'organization_id' => $org->getKey(), 'user_id' => $member->getKey(), 'role' => 'member',
        ]);

        $p = $this->authorize($owner, strtoupper((string) $org->getKey()));
        self::assertTrue($p->canManage);
        self::assertSame((string) $org->getKey(), $p->organizationId);

        $q = $this->authorize($member, (string) $org->getKey());
        self::assertFalse($q->canManage);
    }

    public function test_authorizer_is_not_bound_so_routes_stay_unavailable(): void
    {
        self::assertFalse($this->app->bound(OmniDeskApiAuthorizer::class));
    }

    private function authorize(?User $user, ?string $organizationId): OmniDeskApiPrincipal
    {
        $request = Request::create('/api/omnidesk/v1/activations/x', 'GET');
        if ($organizationId !== null) {
            $request->headers->set(OmniDeskMembershipApiAuthorizer::ORGANIZATION_HEADER, $organizationId);
        }
        $request->setUserResolver(static fn () => $user);

        return app(OmniDeskMembershipApiAuthorizer::class)->authorize($request);
    }

    /**
     * @param  array<string, string>  $f
     * @param  array<string, string>  $d
     * @return array<string, mixed>
     */
    private function bind(array $f, array $d, ?int $limit): array
    {
        return app(OmniDeskActivationBindingStore::class)->bind(
            $d['activation_id'], $f['license_id'], $f['entitlement_id'], $f['organization_id'],
            $d['public_key'], $d['fingerprint'], $d['installation_id'], $d['idempotency_key'],
            'test-actor', $limit,
        );
    }

    /**
     * @param  array<string, string>  $f
     * @return array<string, string>
     */
    private function device(array $f, string $label): array
    {
        $activationId = (string) Str::uuid();
        DB::table('kslp_activations')->insert([
            'id' => $activationId,
            'license_id' => $f['license_id'],
            'server_identity' => 'seat-test-'.$label.'-'.$activationId,
            'machine_identity_hash' => hash('sha256', $label.$activationId),
            'idempotency_key' => 'generic-activation-'.Str::uuid(),
            'activated_at' => now(),
            'deactivated_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $raw = sodium_crypto_sign_publickey(sodium_crypto_sign_keypair());

        return [
            'activation_id' => $activationId,
            'public_key' => rtrim(strtr(base64_encode($raw), '+/', '-_'), '='),
            'fingerprint' => 'sha256:'.hash('sha256', $raw),
            'installation_id' => 'install-'.$label.'-'.substr($activationId, 0, 8),
            'idempotency_key' => 'omnidesk-binding-'.$label.'-'.$activationId,
        ];
    }

    /**
     * @return array<string, string>
     */
    private function tenant(): array
    {
        $organization = Organization::query()->create(['name' => 'Seat tenant '.Str::random(6)]);
        $product = Product::query()->firstOrCreate(['slug' => OmniDeskLicenseContract::PRODUCT_SLUG], [
            'name' => 'KMJ OmniDesk',
            'status' => 'active',
            'lifecycle' => 'pre-alpha',
            'is_public' => false,
            'purchase_enabled' => false,
            'licensing_enabled' => true,
        ]);
        $policy = EntitlementPolicy::query()->firstOrCreate(['code' => 'omnidesk.seat.test'], [
            'product_id' => $product->getKey(),
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
        ]);
        $entitlement = Entitlement::query()->create([
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'policy_id' => $policy->getKey(),
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
            'idempotency_key' => 'omnidesk-seat-entitlement-'.Str::uuid(),
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

        return [
            'license_id' => $licenseId,
            'entitlement_id' => (string) $entitlement->getKey(),
            'organization_id' => (string) $organization->getKey(),
        ];
    }
}
