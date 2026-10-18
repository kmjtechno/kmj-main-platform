<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\Payments\PaymentGatewayReadiness;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ProviderRequest;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
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
            ->where('paymentReadiness.providers.0.webhook_secret_stored', true)
            ->where('paymentReadiness.providers.0.webhook_verification_configured', false)
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

    public function test_guest_regular_user_and_owner_without_keys_cannot_probe_provider(): void
    {
        Http::preventStrayRequests();
        Http::fake();

        $this->post('/operator/payments/gateways/razorpay/test-connection')
            ->assertRedirect('/login');

        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($regular)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/payments/gateways/razorpay/test-connection')
            ->assertForbidden();

        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/payments/gateways/razorpay/test-connection')
            ->assertSessionHasErrors('sandbox_probe');

        Http::assertNothingSent();
    }

    public function test_owner_razorpay_test_connection_creates_only_a_nonpayable_sandbox_probe(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/razorpay', [
                ...$this->payload(),
                'client_id' => 'rzp_test_ABC123',
                'client_secret' => 'sandbox_secret_12345678',
            ])->assertRedirect('/operator/payments');

        Http::preventStrayRequests();
        Http::fake(['api.razorpay.com/v1/orders' => function (ProviderRequest $request) {
            return Http::response([
                'id' => 'order_TEST123',
                'receipt' => $request['receipt'],
                'currency' => 'INR',
                'amount' => 100,
                'status' => 'created',
                'amount_paid' => 0,
                'amount_due' => 100,
            ], 200);
        }]);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/payments/gateways/razorpay/test-connection')
            ->assertRedirect('/operator/payments');

        Http::assertSent(fn (ProviderRequest $request): bool => $request->method() === 'POST'
            && $request->url() === 'https://api.razorpay.com/v1/orders'
            && $request['amount'] === 100
            && $request['currency'] === 'INR'
            && $request['partial_payment'] === false
            && str_starts_with((string) $request['receipt'], 'kmjcb_probe_'));
        self::assertSame('sandbox_order_created_only', OperatorActionAudit::query()
            ->where('action', 'payment_gateway.sandbox_order_probe')
            ->firstOrFail()->outcome);
        self::assertFalse((bool) app(PaymentGatewayReadiness::class)->snapshot()['live_charging_enabled']);
    }

    public function test_owner_cashfree_probe_requires_authorized_phone_and_never_creates_a_live_payment(): void
    {
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/cashfree', [
                ...$this->payload(),
                'client_id' => 'test_cashfree_id',
                'client_secret' => 'test_cashfree_secret',
            ])->assertRedirect('/operator/payments');

        Http::preventStrayRequests();
        Http::fake(['https://sandbox.cashfree.com/pg/orders' => function (ProviderRequest $request) {
            return Http::response([
                'order_id' => $request['order_id'],
                'order_currency' => 'INR',
                'order_amount' => 1,
                'payment_session_id' => 'test_session_01234567890',
            ], 200);
        }]);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/payments/gateways/cashfree/test-connection', [])
            ->assertSessionHasErrors('test_phone');
        Http::assertNothingSent();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/payments/gateways/cashfree/test-connection', [
                'test_phone' => '9876543210',
            ])->assertRedirect('/operator/payments');

        Http::assertSent(fn (ProviderRequest $request): bool => $request->method() === 'POST'
            && $request->url() === 'https://sandbox.cashfree.com/pg/orders'
            && $request['order_amount'] === 1.0
            && $request['order_currency'] === 'INR'
            && $request['customer_details']['customer_phone'] === '9876543210');

        $audit = OperatorActionAudit::query()
            ->where('action', 'payment_gateway.sandbox_order_probe')
            ->firstOrFail();
        self::assertFalse((bool) $audit->metadata['charged']);
        self::assertFalse((bool) $audit->metadata['entitlement_issued']);
        self::assertStringNotContainsString('9876543210', json_encode($audit->metadata, JSON_THROW_ON_ERROR));
    }

    public function test_sandbox_probe_failure_never_flashes_gateway_secrets_or_claims_verified(): void
    {
        $owner = $this->owner();
        $secret = 'failure_should_be_redacted';
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->put('/operator/payments/gateways/razorpay', [
                ...$this->payload(),
                'client_id' => 'rzp_test_ABC123',
                'client_secret' => $secret,
            ])->assertRedirect('/operator/payments');

        Http::preventStrayRequests();
        Http::fake(['https://api.razorpay.com/v1/orders' => Http::response([
            'error' => $secret,
        ], 403)]);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/payments/gateways/razorpay/test-connection')
            ->assertSessionHasErrors('sandbox_probe');

        self::assertSame(0, OperatorActionAudit::query()
            ->where('action', 'payment_gateway.sandbox_order_probe')->count());
        self::assertStringNotContainsString($secret, json_encode(session()->get('errors'), JSON_THROW_ON_ERROR));
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
