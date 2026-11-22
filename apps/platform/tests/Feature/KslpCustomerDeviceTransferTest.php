<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpActivationProof;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class KslpCustomerDeviceTransferTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        config()->set('services.kmj_customer_device_transfer.enabled', true);
    }

    /** @return array{string, string} */
    private function identity(): array
    {
        $pair = sodium_crypto_sign_keypair();
        $public = sodium_crypto_sign_publickey($pair);
        $secret = sodium_crypto_sign_secretkey($pair);

        return ['ed25519:'.rtrim(strtr(base64_encode($public), '+/', '-_'), '='), $secret];
    }

    /** @return array{string, string, string} */
    private function proof(string $licenseId, string $identity, string $secret): array
    {
        $challenge = app(KslpActivationProof::class)->challenge($licenseId, $identity);
        $message = 'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$challenge['nonce'];
        $signature = rtrim(strtr(base64_encode(
            sodium_crypto_sign_detached($message, $secret),
        ), '+/', '-_'), '=');

        return [$challenge['challenge_id'], $challenge['nonce'], $signature];
    }

    /** @return array{User, string, string, string} */
    private function activeAccount(): array
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        $license = app(KslpLicenseControlPlane::class)->issue(
            (string) $customer->getKey(), 'professional', 'test-owner', 'verified purchase fixture',
        );

        [$identity, $secret] = $this->identity();
        [$challenge, $nonce, $signature] = $this->proof($license['id'], $identity, $secret);
        $activation = app(KslpLicenseControlPlane::class)->activate(
            $license['id'], $identity, str_repeat('a', 64), 'first-device',
            'test-owner', $challenge, $nonce, $signature,
        );

        // Fixtures only: real customers must wait for a 24-hour cooldown.
        DB::table('kslp_activations')->where('id', $activation['id'])->update([
            'activated_at' => now()->subDays(2),
        ]);

        return [$customer, $license['id'], $activation['id'], $identity];
    }

    private function signedIn(User $customer): void
    {
        $this->actingAs($customer)->withSession(['auth.password_confirmed_at' => time()]);
    }

    public function test_guest_and_unverified_accounts_cannot_request_transfer(): void
    {
        $licenseId = (string) Str::uuid();
        $this->post("/licensing/devices/transfer/{$licenseId}/challenge", [])
            ->assertRedirect('/login');

        $unverified = User::factory()->create(['email_verified_at' => null]);
        $this->actingAs($unverified)->withSession(['auth.password_confirmed_at' => time()])
            ->post("/licensing/devices/transfer/{$licenseId}/challenge", [
                'server_identity' => $this->identity()[0],
            ])->assertRedirect(route('verification.notice'));
    }

    public function test_transfer_endpoints_are_default_off_even_for_verified_user(): void
    {
        [$user, $licenseId] = $this->activeAccount();
        $this->signedIn($user);
        config()->set('services.kmj_customer_device_transfer.enabled', false);
        $this->post("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $this->identity()[0],
        ])->assertStatus(503);
        $this->post("/licensing/devices/transfer/{$licenseId}/complete", [])
            ->assertStatus(503);
        $this->assertDatabaseCount('kslp_activation_challenges', 1);
    }

    public function test_other_customers_cannot_challenge_or_transfer_a_foreign_license(): void
    {
        [, $licenseId, $original] = $this->activeAccount();
        $other = User::factory()->create(['email_verified_at' => now()]);
        $this->signedIn($other);
        [$identity] = $this->identity();

        $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $identity,
        ])->assertStatus(409)->assertJson(['error' => 'KSLP_DEVICE_TRANSFER_DENIED']);

        $this->assertDatabaseHas('kslp_activations', [
            'id' => $original, 'deactivated_at' => null,
        ]);
    }

    public function test_signed_proof_transfers_one_seat_and_retry_never_redebits_sequence(): void
    {
        [$user, $licenseId, $original] = $this->activeAccount();
        $this->signedIn($user);
        [$identity, $secret] = $this->identity();

        $challenge = $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $identity,
        ])->assertOk()->assertJsonPath('status', 'proof_required')->json();

        $signature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$challenge['nonce'],
            $secret,
        )), '+/', '-_'), '=');
        $payload = [
            'server_identity' => $identity,
            'machine_hash' => str_repeat('b', 64),
            'request_id' => (string) Str::uuid(),
            'challenge_id' => $challenge['challenge_id'],
            'nonce' => $challenge['nonce'],
            'signature' => $signature,
            'reason' => 'Customer replaced workstation after disk failure',
        ];

        $first = $this->postJson("/licensing/devices/transfer/{$licenseId}/complete", $payload)
            ->assertOk()
            ->assertJsonPath('signed_lease_issued', false)
            ->assertJsonPath('status', 'device_transfer_recorded_pending_signed_lease')
            ->json();

        $this->assertDatabaseHas('kslp_activations', [
            'id' => $original, 'license_id' => $licenseId,
        ]);
        self::assertNotNull(DB::table('kslp_activations')->where('id', $original)->value('deactivated_at'));
        $this->assertDatabaseHas('kslp_activations', [
            'id' => $first['activation_id'], 'license_id' => $licenseId,
            'deactivated_at' => null,
        ]);
        $this->assertDatabaseHas('kslp_licenses', ['id' => $licenseId, 'sequence' => 2]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $licenseId, 'action' => 'transferred',
            'actor_id' => 'customer:'.$user->getKey(),
        ]);

        $retry = $this->postJson("/licensing/devices/transfer/{$licenseId}/complete", $payload)
            ->assertOk()->json();
        self::assertSame($first['activation_id'], $retry['activation_id']);
        $this->assertDatabaseHas('kslp_licenses', ['id' => $licenseId, 'sequence' => 2]);
        self::assertSame(1, DB::table('kslp_license_events')->where('license_id', $licenseId)
            ->where('action', 'transferred')->count());
    }

    public function test_invalid_signature_rolls_back_old_seat_and_unconsumed_challenge(): void
    {
        [$user, $licenseId, $original] = $this->activeAccount();
        $this->signedIn($user);
        [$identity] = $this->identity();
        [, $wrongSecret] = $this->identity();

        $challenge = $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $identity,
        ])->assertOk()->json();
        $signature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$challenge['nonce'],
            $wrongSecret,
        )), '+/', '-_'), '=');

        $this->postJson("/licensing/devices/transfer/{$licenseId}/complete", [
            'server_identity' => $identity,
            'machine_hash' => str_repeat('b', 64),
            'request_id' => (string) Str::uuid(),
            'challenge_id' => $challenge['challenge_id'],
            'nonce' => $challenge['nonce'],
            'signature' => $signature,
            'reason' => 'Lost device and customer support approved case',
        ])->assertStatus(409)->assertJsonPath('error', 'KSLP_DEVICE_TRANSFER_DENIED');

        $this->assertDatabaseHas('kslp_activations', [
            'id' => $original, 'deactivated_at' => null,
        ]);
        $this->assertDatabaseHas('kslp_licenses', ['id' => $licenseId, 'sequence' => 1]);
        $this->assertDatabaseHas('kslp_activation_challenges', [
            'id' => $challenge['challenge_id'], 'used_at' => null,
        ]);
        self::assertSame(0, DB::table('kslp_license_events')
            ->where('license_id', $licenseId)->where('action', 'transferred')->count());
    }

    public function test_recent_activation_and_trial_cannot_reset_their_device(): void
    {
        [$user, $licenseId, $activation] = $this->activeAccount();
        $this->signedIn($user);
        DB::table('kslp_activations')->where('id', $activation)->update(['activated_at' => now()]);

        $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $this->identity()[0],
        ])->assertStatus(409);

        DB::table('kslp_activations')->where('id', $activation)
            ->update(['activated_at' => now()->subDays(2)]);
        DB::table('kslp_licenses')->where('id', $licenseId)->update(['plan' => 'trial']);
        $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $this->identity()[0],
        ])->assertStatus(409);
    }

    public function test_second_transfer_within_cooldown_is_denied_without_new_proof(): void
    {
        [$user, $licenseId] = $this->activeAccount();
        $this->signedIn($user);
        DB::table('kslp_license_events')->insert([
            'license_id' => $licenseId, 'actor_id' => (string) $user->getKey(),
            'action' => 'transferred', 'reason' => 'Previous approved transfer',
            'correlation_id' => (string) Str::uuid(),
            'metadata' => null, 'created_at' => now(),
        ]);
        $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $this->identity()[0],
        ])->assertStatus(409)->assertJsonPath('error', 'KSLP_DEVICE_TRANSFER_DENIED');
    }

    public function test_cross_product_transfer_is_denied_before_any_challenge(): void
    {
        [$user, $licenseId] = $this->activeAccount();
        $this->signedIn($user);
        DB::table('kslp_licenses')->where('id', $licenseId)->update(['product' => 'KMJ_OMNIDESK']);
        $count = DB::table('kslp_activation_challenges')->count();
        $this->postJson("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $this->identity()[0],
        ])->assertStatus(409);
        self::assertSame($count, DB::table('kslp_activation_challenges')->count());
    }

    public function test_password_confirmation_is_required_before_transfer(): void
    {
        [$user, $licenseId] = $this->activeAccount();
        $this->actingAs($user);
        $this->post("/licensing/devices/transfer/{$licenseId}/challenge", [
            'server_identity' => $this->identity()[0],
        ])->assertRedirect(route('password.confirm'));
    }
}
