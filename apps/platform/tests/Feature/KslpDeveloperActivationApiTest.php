<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class KslpDeveloperActivationApiTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{string, string} */
    private function developerKey(): array
    {
        $owner = User::factory()->create();
        $this->actingAs($owner)->post('/organizations', ['name' => 'SDK Development Lab']);
        $org = (string) DB::table('organization_memberships')
            ->where('user_id', $owner->id)->value('organization_id');

        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->subscribe($org, 'professional', 2, 20);
        $authority->registerProduct($org, 'DEVELOPER.APP', 'Developer App');
        $key = app(KslpDeveloperKeys::class)->issue(
            $org, 'DEVELOPER.APP', 'customer-1', 'trial', (string) $owner->id,
        );

        return [$key['key'], $key['license_id']];
    }

    /** @return array{string, string} */
    private function device(): array
    {
        $pair = sodium_crypto_sign_keypair();
        $secret = sodium_crypto_sign_secretkey($pair);
        $public = sodium_crypto_sign_publickey($pair);

        return ['ed25519:'.rtrim(strtr(base64_encode($public), '+/', '-_'), '='), $secret];
    }

    public function test_first_login_requires_valid_device_signature_and_persists_consent_metadata(): void
    {
        config()->set('services.kmj_developer_licensing.enabled', true);
        [$licenseKey, $licenseId] = $this->developerKey();
        [$device, $secret] = $this->device();

        $challenge = $this->postJson('/api/v1/kslp/developer/activation/challenge', [
            'license_key' => $licenseKey,
            'server_identity' => $device,
        ])->assertOk()->assertHeader('Cache-Control', 'no-store')
            ->assertJsonStructure(['challenge_id', 'nonce', 'expires_in', 'license_id', 'product'])
            ->assertJsonPath('license_id', $licenseId)
            ->assertJsonPath('product', 'DEVELOPER.APP')
            ->json();

        $signature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$challenge['nonce'],
            $secret,
        )), '+/', '-_'), '=');

        $request = [
            'license_key' => $licenseKey,
            'server_identity' => $device,
            'machine_hash' => hash('sha256', 'random-install-identifier'),
            'request_id' => 'activation-request-000001',
            'challenge_id' => $challenge['challenge_id'],
            'nonce' => $challenge['nonce'],
            'signature' => $signature,
            'metadata_consent' => true,
            'platform' => 'windows',
            'app_version' => '2.1.0',
        ];

        $activation = $this->postJson('/api/v1/kslp/developer/activation/complete', $request)
            ->assertOk()->assertJsonPath('device_registered', true)
            ->assertJsonPath('signed_lease_issued', false)
            ->json();

        $this->assertDatabaseHas('kslp_license_keys', [
            'license_id' => $licenseId,
            'client_platform' => 'windows',
            'client_app_version' => '2.1.0',
        ]);
        self::assertNotNull(DB::table('kslp_license_keys')->where('license_id', $licenseId)->value('first_activated_at'));

        $retry = $this->postJson('/api/v1/kslp/developer/activation/complete', $request)
            ->assertOk()->json();
        self::assertSame($activation['activation_id'], $retry['activation_id']);
        self::assertSame(1, DB::table('kslp_activations')->where('license_id', $licenseId)->count());

        // Retrying with withdrawn consent must erase optional diagnostics,
        // while preserving the same verified activation and license.
        $request['metadata_consent'] = false;
        $this->postJson('/api/v1/kslp/developer/activation/complete', $request)
            ->assertOk()
            ->assertJsonPath('activation_id', $activation['activation_id']);
        $afterWithdrawal = DB::table('kslp_license_keys')->where('license_id', $licenseId)->first();
        self::assertNull($afterWithdrawal->client_platform);
        self::assertNull($afterWithdrawal->client_app_version);
        self::assertNull($afterWithdrawal->metadata_consented_at);
    }

    public function test_first_login_without_consent_does_not_store_optional_device_metadata(): void
    {
        config()->set('services.kmj_developer_licensing.enabled', true);
        [$licenseKey, $licenseId] = $this->developerKey();
        [$device, $secret] = $this->device();
        $challenge = $this->postJson('/api/v1/kslp/developer/activation/challenge', [
            'license_key' => $licenseKey, 'server_identity' => $device,
        ])->assertOk()->json();
        $signature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$challenge['nonce'], $secret,
        )), '+/', '-_'), '=');

        $this->postJson('/api/v1/kslp/developer/activation/complete', [
            'license_key' => $licenseKey,
            'server_identity' => $device,
            'machine_hash' => hash('sha256', 'install-id'),
            'request_id' => 'activation-request-000002',
            'challenge_id' => $challenge['challenge_id'],
            'nonce' => $challenge['nonce'],
            'signature' => $signature,
            'metadata_consent' => false,
            'platform' => 'linux',
            'app_version' => '3.0.0',
        ])->assertOk();

        $record = DB::table('kslp_license_keys')->where('license_id', $licenseId)->first();
        self::assertNotNull($record->first_activated_at);
        self::assertNull($record->client_platform);
        self::assertNull($record->client_app_version);
        self::assertNull($record->metadata_consented_at);
    }

    public function test_forged_signature_is_rejected_without_creating_activation(): void
    {
        config()->set('services.kmj_developer_licensing.enabled', true);
        [$licenseKey, $licenseId] = $this->developerKey();
        [$device] = $this->device();
        [, $attackerSecret] = $this->device();
        $challenge = $this->postJson('/api/v1/kslp/developer/activation/challenge', [
            'license_key' => $licenseKey, 'server_identity' => $device,
        ])->assertOk()->json();
        $signature = rtrim(strtr(base64_encode(sodium_crypto_sign_detached(
            'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$challenge['nonce'], $attackerSecret,
        )), '+/', '-_'), '=');

        $this->postJson('/api/v1/kslp/developer/activation/complete', [
            'license_key' => $licenseKey,
            'server_identity' => $device,
            'machine_hash' => hash('sha256', 'install-id'),
            'request_id' => 'activation-request-000003',
            'challenge_id' => $challenge['challenge_id'],
            'nonce' => $challenge['nonce'],
            'signature' => $signature,
            'metadata_consent' => false,
        ])->assertStatus(422)->assertJsonPath('error', 'KSLP_ACTIVATION_DENIED');

        $this->assertDatabaseCount('kslp_activations', 0);
    }

    public function test_unknown_key_and_default_off_mode_fail_closed(): void
    {
        $this->postJson('/api/v1/kslp/developer/activation/challenge', [
            'license_key' => 'KMJ1-'.str_repeat('A', 43),
            'server_identity' => $this->device()[0],
        ])->assertStatus(503);

        config()->set('services.kmj_developer_licensing.enabled', true);
        $this->postJson('/api/v1/kslp/developer/activation/challenge', [
            'license_key' => 'KMJ1-'.str_repeat('A', 43),
            'server_identity' => $this->device()[0],
        ])->assertStatus(422)->assertJsonPath('error', 'KSLP_ACTIVATION_DENIED');
    }
}
