<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class OwnerPaymentGatewaySettingsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_gateway_settings_are_denied_to_guest_regular_user_and_owner_without_passkey(): void
    {
        $url = '/operator/payments/gateways/razorpay';
        $data = $this->payload();

        $this->put($url, $data)->assertRedirect('/login');
        $this->get('/operator/payments')->assertRedirect('/login');

        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($regular)->withSession(['auth.password_confirmed_at' => time()])
            ->put($url, $data)->assertForbidden();

        $untrustedOwner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        $this->actingAs($untrustedOwner)->withSession(['auth.password_confirmed_at' => time()])
            ->put($url, $data)->assertForbidden();

        $this->assertDatabaseCount('payment_gateway_settings', 0);
    }

    public function test_owner_can_save_write_only_encrypted_test_keys_and_sanitized_status(): void
    {
        $owner = $this->owner();
        $id = 'rzp_test_demo_key_12345';
        $secret = 'sandbox_secret_example_12345';
        $webhook = 'sandbox_webhook_secret_12345';

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/razorpay', [
                ...$this->payload(),
                'client_id' => $id,
                'client_secret' => $secret,
                'webhook_secret' => $webhook,
            ])->assertRedirect('/operator/payments');

        $row = DB::table('payment_gateway_settings')->where('provider', 'razorpay')->first();
        self::assertNotNull($row);
        self::assertSame('sandbox', $row->environment);
        self::assertSame('owner_reports_approved', $row->merchant_status);
        self::assertTrue((bool) $row->international_requested);
        self::assertNotSame($id, $row->encrypted_client_id);
        self::assertNotSame($secret, $row->encrypted_client_secret);
        self::assertNotSame($webhook, $row->encrypted_webhook_secret);
        self::assertSame($secret, Crypt::decryptString($row->encrypted_client_secret));

        $response = $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/payments');
        $response->assertOk()->assertInertia(fn (Assert $page) => $page
            ->component('operator-payments')
            ->has('gatewaySettings', 2)
            ->where('gatewaySettings.1.client_id_stored', true)
            ->where('gatewaySettings.1.client_secret_stored', true)
            ->where('gatewaySettings.1.webhook_secret_stored', true)
            ->where('gatewaySettings.1.live_charging_enabled', false)
            ->where('gatewaySettings.1.sandbox_transaction_verified', false)
            ->where('paymentReadiness.providers.1.webhook_secret_stored', true)
            ->where('paymentReadiness.providers.1.webhook_verification_configured', false)
            ->where('paymentReadiness.live_charging_enabled', false));
        $response->assertDontSee($id)
            ->assertDontSee($secret)
            ->assertDontSee($webhook);

        $audit = OperatorActionAudit::query()->latest('id')->firstOrFail();
        self::assertSame('payment_gateway.sandbox_settings_saved', $audit->action);
        self::assertSame(['client_id', 'client_secret', 'webhook_secret'], $audit->metadata['changed_secret_fields']);
        self::assertStringNotContainsString($secret, json_encode($audit->metadata, JSON_THROW_ON_ERROR));
    }

    public function test_empty_fields_preserve_secrets_and_revocation_removes_them(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/cashfree', [
                ...$this->payload(),
                'client_id' => 'sandbox_cashfree_client',
                'client_secret' => 'sandbox_cashfree_secret',
            ])->assertRedirect('/operator/payments');

        $before = DB::table('payment_gateway_settings')->where('provider', 'cashfree')->first();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/cashfree', [
                ...$this->payload(),
                'merchant_status' => 'verification_pending',
                'client_id' => '',
                'client_secret' => '',
            ])->assertRedirect('/operator/payments');

        $after = DB::table('payment_gateway_settings')->where('provider', 'cashfree')->first();
        self::assertSame($before->encrypted_client_id, $after->encrypted_client_id);
        self::assertSame($before->encrypted_client_secret, $after->encrypted_client_secret);
        self::assertSame('verification_pending', $after->merchant_status);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->delete('/operator/payments/gateways/cashfree/credentials')
            ->assertRedirect('/operator/payments');

        $revoked = DB::table('payment_gateway_settings')->where('provider', 'cashfree')->first();
        self::assertNull($revoked->encrypted_client_id);
        self::assertNull($revoked->encrypted_client_secret);
        self::assertNull($revoked->encrypted_webhook_secret);
        $this->assertDatabaseHas('operator_action_audits', [
            'action' => 'payment_gateway.sandbox_credentials_revoked',
            'outcome' => 'revoked',
        ]);
    }

    public function test_live_mode_invalid_provider_and_live_razorpay_key_fail_closed(): void
    {
        $owner = $this->owner();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/razorpay', [
                ...$this->payload(),
                'environment' => 'live',
            ])->assertSessionHasErrors('environment');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/razorpay', [
                ...$this->payload(),
                'client_id' => 'rzp_live_disallowed_key',
            ])->assertSessionHasErrors('client_id');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/paypal', $this->payload())->assertNotFound();

        $this->assertDatabaseCount('payment_gateway_settings', 0);
    }

    public function test_secret_fields_are_never_flashed_to_session_after_validation_failure(): void
    {
        $owner = $this->owner();
        $secret = 'TEST_SECRET_NEVER_FLASHED';
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->from('/operator/payments')
            ->put('/operator/payments/gateways/razorpay', [
                ...$this->payload(),
                'merchant_status' => 'bogus',
                'client_secret' => $secret,
            ])->assertSessionHasErrors('merchant_status');

        $flashed = session()->get('_old_input', []);
        self::assertArrayNotHasKey('client_secret', $flashed);
        self::assertArrayNotHasKey('client_id', $flashed);
        self::assertArrayNotHasKey('webhook_secret', $flashed);
        self::assertStringNotContainsString($secret, json_encode($flashed, JSON_THROW_ON_ERROR));
    }

    public function test_staged_deployment_without_settings_table_is_readable_but_rejects_writes(): void
    {
        $owner = $this->owner();
        Schema::dropIfExists('payment_gateway_settings');

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/payments')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-payments')
                ->where('gatewaySettings.0.storage_ready', false)
                ->where('gatewaySettings.1.storage_ready', false)
                ->where('paymentReadiness.live_charging_enabled', false));

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/razorpay', $this->payload())
            ->assertStatus(503);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->delete('/operator/payments/gateways/razorpay/credentials')
            ->assertStatus(503);
    }

    /** @return array<string, bool|string> */
    private function payload(): array
    {
        return [
            'environment' => 'sandbox',
            'merchant_status' => 'owner_reports_approved',
            'international_requested' => true,
        ];
    }

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->getKey(),
            'name' => 'Owner passkey',
            'credential_id' => 'owner-payments-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
