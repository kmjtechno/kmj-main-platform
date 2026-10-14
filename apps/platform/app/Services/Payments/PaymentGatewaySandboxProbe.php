<?php

declare(strict_types=1);

namespace App\Services\Payments;

use App\Models\OperatorActionAudit;
use App\Models\User;
use DomainException;
use Illuminate\Support\Str;
use Throwable;

/**
 * Explicit, owner-initiated test-order probe. No payment is captured and
 * no commercial order, entitlement, or license is created here.
 */
final class PaymentGatewaySandboxProbe
{
    public function __construct(
        private readonly OwnerPaymentGatewaySettings $settings,
        private readonly RazorpaySandboxOrderClient $razorpay,
        private readonly CashfreeSandboxOrderClient $cashfree,
    ) {}

    public function run(User $actor, string $provider, ?string $testPhone = null): void
    {
        if (! in_array($provider, ['razorpay', 'cashfree'], true)) {
            throw new DomainException('SANDBOX_PROBE_UNSUPPORTED_PROVIDER');
        }

        // Credential decryption is performed only after route owner/passkey checks.
        $credentials = $this->settings->sandboxCredentials($provider);
        $id = 'kmjcb_probe_'.strtolower(Str::random(12));

        // These requests create ONLY a sandbox provider order for INR 1.
        // No payment session is returned to the browser and no customer is charged.
        try {
            if ($provider === 'razorpay') {
                $this->razorpay->create(
                    $id,
                    100,
                    'INR',
                    $credentials['client_id'],
                    $credentials['client_secret'],
                );
            } else {
                if (! is_string($testPhone) || ! preg_match('/\A[6-9][0-9]{9}\z/D', $testPhone)) {
                    throw new DomainException('SANDBOX_PROBE_TEST_PHONE_REQUIRED');
                }

                $this->cashfree->create(
                    $id,
                    100,
                    'INR',
                    'kmj_cb_probe',
                    $testPhone,
                    $credentials['client_id'],
                    $credentials['client_secret'],
                );
            }
        } catch (Throwable $error) {
            // Never let transport/provider exception details leak stored secrets.
            throw new DomainException('SANDBOX_PROBE_UNVERIFIED', previous: $error);
        }

        OperatorActionAudit::query()->create([
            'actor_user_id' => $actor->getKey(),
            'action' => 'payment_gateway.sandbox_order_probe',
            'outcome' => 'sandbox_order_created_only',
            'metadata' => [
                'provider' => $provider,
                'charged' => false,
                'entitlement_issued' => false,
                'live_charging_enabled' => false,
            ],
        ]);
    }
}
