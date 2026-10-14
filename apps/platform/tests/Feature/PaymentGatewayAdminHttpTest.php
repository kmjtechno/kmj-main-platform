<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia;
use Tests\TestCase;

final class PaymentGatewayAdminHttpTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_guests_cannot_view_merchant_configuration(): void
    {
        $this->get('/operator/payments')->assertRedirect('/login');
    }

    public function test_normal_account_cannot_view_merchant_configuration(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/payments')
            ->assertForbidden();
    }

    public function test_owner_without_registered_passkey_cannot_view_merchant_configuration(): void
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/payments')
            ->assertForbidden();
    }

    public function test_verified_owner_sees_only_sanitized_non_billing_status(): void
    {
        $owner = $this->platformOwner();
        config()->set('payment-providers.providers.cashfree.client_id', 'TEST-CASHFREE-CLIENT-ID');
        config()->set('payment-providers.providers.cashfree.client_secret', 'TOP-SECRET-CASHFREE-123');
        config()->set('payment-providers.live_charging_enabled', true);

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/payments')
            ->assertOk()
            ->assertInertia(fn (AssertableInertia $page) => $page
                ->component('operator-payments')
                ->where('paymentReadiness.live_charging_enabled', false)
                ->has('paymentReadiness.providers', 5)
                ->where('paymentReadiness.providers.1.id', 'cashfree')
                ->where('paymentReadiness.providers.1.sandbox_credentials_present', true)
                ->where('paymentReadiness.providers.1.webhook_secret_stored', true)
                ->where('paymentReadiness.providers.1.webhook_verification_configured', false)
                ->where('paymentReadiness.providers.1.live_transaction_verified', false))
            ->assertDontSee('TOP-SECRET-CASHFREE-123')
            ->assertDontSee('TEST-CASHFREE-CLIENT-ID');
    }

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
}
