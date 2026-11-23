<?php

declare(strict_types=1);

namespace App\Services\Payments;

/**
 * BOUND ONLY after genuine merchant onboarding and server-to-server LIVE
 * capture/refund verification, with secrets in the isolated owner vault.
 * Deliberately no implementation or default Laravel binding is provided:
 * sandbox Razorpay adapters MUST NOT be promoted to production authority.
 */
interface OmniDeskVerifiedLivePaymentSource
{
    public function verifyCaptured(string $providerOrderId, string $paymentReference): OmniDeskVerifiedLiveCapture;
}
