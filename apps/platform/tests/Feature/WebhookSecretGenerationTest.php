<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

final class WebhookSecretGenerationTest extends TestCase
{
    use RefreshDatabase;

    private const URL = '/operator/payments/gateways/razorpay/webhook-secret';

    private function platformOwner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'KMJ payment admin passkey',
            'credential_id' => 'payment-admin-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }

    private function generate(User $owner): TestResponse
    {
        return $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(self::URL);
    }

    private function sendSigned(string $secret): int
    {
        $body = json_encode(['event' => 'payment.captured', 'payload' => ['payment' => ['entity' => ['id' => 'pay_GEN1', 'order_id' => 'order_GEN1']]]], JSON_THROW_ON_ERROR);

        return $this->call('POST', '/webhooks/payments/razorpay', [], [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_X_RAZORPAY_SIGNATURE' => hash_hmac('sha256', $body, $secret),
            'HTTP_X_RAZORPAY_EVENT_ID' => 'evt_gen_'.Str::random(6),
        ], $body)->getStatusCode();
    }

    public function test_only_a_password_confirmed_platform_owner_can_generate(): void
    {
        $this->postJson(self::URL)->assertUnauthorized();

        $normal = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($normal)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(self::URL)->assertForbidden();

        $owner = $this->platformOwner();
        $this->actingAs($owner)->postJson(self::URL)->assertStatus(423);

        $this->assertSame(0, DB::table('payment_gateway_settings')->count());
    }

    public function test_generated_secret_is_returned_once_stored_encrypted_and_never_audited_or_in_session(): void
    {
        $owner = $this->platformOwner();

        $response = $this->generate($owner)->assertOk();
        $secret = $response->json('webhook_secret');

        $this->assertMatchesRegularExpression('/\Awhsec_[a-f0-9]{48}\z/', $secret);
        $this->assertStringContainsString('no-store', (string) $response->headers->get('Cache-Control'));

        $stored = DB::table('payment_gateway_settings')->where('provider', 'razorpay')->first();
        $this->assertNotSame($secret, $stored->encrypted_webhook_secret);
        $this->assertSame($secret, Crypt::decryptString($stored->encrypted_webhook_secret));

        $audit = OperatorActionAudit::query()->where('action', 'payment_gateway.webhook_secret_generated')->firstOrFail();
        $this->assertStringNotContainsString($secret, json_encode($audit->toArray(), JSON_THROW_ON_ERROR));
        $this->assertStringNotContainsString($secret, json_encode(session()->all(), JSON_THROW_ON_ERROR));
    }

    public function test_generated_secret_verifies_real_signed_webhooks_end_to_end(): void
    {
        $secret = $this->generate($this->platformOwner())->json('webhook_secret');

        $this->assertSame(200, $this->sendSigned($secret));
        $this->assertSame(1, DB::table('payment_webhook_events')->count());
    }

    public function test_regeneration_replaces_only_the_secret_and_retires_the_old_one(): void
    {
        $owner = $this->platformOwner();
        DB::table('payment_gateway_settings')->insert([
            'provider' => 'razorpay',
            'environment' => 'sandbox',
            'merchant_status' => 'verification_pending',
            'international_requested' => true,
            'encrypted_client_id' => Crypt::encryptString('rzp_test_KEEP123'),
            'encrypted_webhook_secret' => Crypt::encryptString('old-secret-value'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $secret = $this->generate($owner)->json('webhook_secret');

        $row = DB::table('payment_gateway_settings')->where('provider', 'razorpay')->first();
        $this->assertSame('verification_pending', $row->merchant_status);
        $this->assertTrue((bool) $row->international_requested);
        $this->assertSame('rzp_test_KEEP123', Crypt::decryptString($row->encrypted_client_id));
        $this->assertSame(401, $this->sendSigned('old-secret-value'));
        $this->assertSame(200, $this->sendSigned($secret));
    }

    public function test_only_razorpay_has_a_separate_webhook_secret(): void
    {
        $owner = $this->platformOwner();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/payments/gateways/cashfree/webhook-secret')->assertNotFound();
        $this->assertSame(0, DB::table('payment_gateway_settings')->count());
    }
}
