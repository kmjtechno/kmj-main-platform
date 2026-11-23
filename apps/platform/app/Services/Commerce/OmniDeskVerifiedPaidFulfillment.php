<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use App\Models\User;
use App\Services\Licensing\OmniDeskLicenseContract;
use App\Services\Payments\OmniDeskVerifiedLiveCapture;
use App\Services\Payments\OmniDeskVerifiedLivePaymentSource;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialLedgerEntry;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

/**
 * After a real LIVE capture, provision one bounded, auditable first-party
 * OmniDesk subscription period in the ONE KSLP licensing authority.
 *
 * No public endpoint accepts an issuer, entitlement or payment proof. The
 * trusted external LIVE payment verifier remains deliberately UNBOUND until
 * a separate owner-approved merchant onboarding and real capture/refund QA.
 * This service NEVER calls a signing key or activates a device.
 */
final class OmniDeskVerifiedPaidFulfillment
{
    private const PLAN_TO_TIER = [
        'omnidesk.professional' => 'professional',
        'omnidesk.business' => 'business',
        'omnidesk.enterprise' => 'enterprise',
    ];

    public const POLICY_CODE = 'omnidesk.paid.remote_access';

    public function __construct(
        private readonly EntitlementIssuer $entitlements,
        private readonly OrganizationCapabilityContext $capabilities,
    ) {}

    /**
     * @return array{commercial_order_id:string,license_id:string,entitlement_id:string,expires_at:string,status:string,already_exists:bool}
     */
    public function fulfill(string $orderId, OmniDeskVerifiedLivePaymentSource $verifier): array
    {
        if (config('omnidesk-licensing.live_paid_fulfillment_enabled', false) !== true
            || config('payment-providers.live_charging_enabled', false) !== true) {
            throw new DomainException('OMNIDESK_PAID_FULFILLMENT_DISABLED');
        }

        $order = DB::table('commerce_orders')->where('id', $orderId)->first();
        if ($order === null || (string) $order->status !== 'confirmed') {
            throw new DomainException('OMNIDESK_PAYMENT_NOT_CONFIRMED');
        }

        $match = [];
        if (preg_match('/\Arazorpay:(pay_[A-Za-z0-9]{1,64})\z/D', (string) $order->confirmation_reference, $match) !== 1) {
            throw new DomainException('OMNIDESK_PAYMENT_REFERENCE_INVALID');
        }
        $paymentReference = $match[1];

        $providerLink = DB::table('commerce_provider_orders')
            ->where('commercial_order_id', $orderId)
            ->where('provider', 'razorpay')
            ->where('environment', 'live')
            ->first();

        if ($providerLink === null) {
            throw new DomainException('OMNIDESK_LIVE_PAYMENT_PROOF_REQUIRED');
        }

        // Cryptographic webhook receipt is a HINT, not final settlement:
        // external LIVE provider server-to-server evidence is mandatory.
        $proof = $verifier->verifyCaptured(
            (string) $providerLink->provider_order_id,
            $paymentReference,
        );
        $this->assertVerifiedPayment($proof, $providerLink, $paymentReference);

        return DB::transaction(function () use ($orderId, $paymentReference, $proof): array {
            $orderRow = DB::table('commerce_orders')
                ->where('id', $orderId)->lockForUpdate()->first();
            if ($orderRow === null || (string) $orderRow->status !== 'confirmed'
                || (string) $orderRow->confirmation_reference !== 'razorpay:'.$paymentReference
                || (string) $orderRow->currency !== $proof->currency
                || (int) $orderRow->amount_minor !== $proof->amountMinor) {
                throw new DomainException('OMNIDESK_PAYMENT_ORDER_CHANGED');
            }

            $snapshotRow = DB::table('commerce_order_plan_snapshots')
                ->where('commercial_order_id', $orderId)->lockForUpdate()->first();
            $link = DB::table('commerce_provider_orders')
                ->where('commercial_order_id', $orderId)
                ->where('provider', 'razorpay')
                ->where('environment', 'live')
                ->lockForUpdate()->first();

            if ($snapshotRow === null || $link === null) {
                throw new DomainException('OMNIDESK_PLAN_OR_PAYMENT_MISSING');
            }

            /** @var array{organization_id:string,product_id:string,plan_id:string,plan_code:string,currency:string,amount_minor:int,billing_interval:string} $snapshot */
            $snapshot = (array) $snapshotRow;
            if ((string) $link->provider_order_id !== $proof->providerOrderId
                || (int) $link->amount_minor !== $proof->amountMinor
                || (string) $link->currency !== $proof->currency
                || (string) $orderRow->product_id !== $snapshot['product_id']
                || (string) $orderRow->organization_id !== $snapshot['organization_id']
                || $snapshot['currency'] !== $proof->currency
                || (int) $snapshot['amount_minor'] !== $proof->amountMinor) {
                throw new DomainException('OMNIDESK_PLAN_OR_PAYMENT_MISMATCH');
            }

            // Require both successful provider reconciliation and the *same*
            // captured provider order/payment. Generic manually confirmed
            // commerce orders are NOT permitted to mint paid licenses.
            $reconciled = DB::table('payment_webhook_events')
                ->where('provider', 'razorpay')
                ->where('provider_order_id', $proof->providerOrderId)
                ->where('provider_payment_id', $paymentReference)
                ->where('processing_status', 'reconciled')
                ->where('processing_note', 'CONFIRMED')
                ->exists();
            if (! $reconciled) {
                throw new DomainException('OMNIDESK_PROVIDER_RECONCILIATION_REQUIRED');
            }

            $existingRow = DB::table('commerce_paid_fulfillments')
                ->where('commercial_order_id', $orderId)->lockForUpdate()->first();
            if ($existingRow !== null) {
                if ((string) $existingRow->provider !== 'razorpay'
                    || (string) $existingRow->provider_order_id !== $proof->providerOrderId
                    || (string) $existingRow->payment_reference !== $paymentReference
                    || (string) $existingRow->organization_id !== $snapshot['organization_id']
                    || (string) $existingRow->plan_id !== $snapshot['plan_id']) {
                    throw new DomainException('OMNIDESK_PAID_FULFILLMENT_CONFLICT');
                }

                return [
                    'commercial_order_id' => $orderId,
                    'license_id' => (string) $existingRow->license_id,
                    'entitlement_id' => (string) $existingRow->entitlement_id,
                    'expires_at' => (string) $existingRow->period_ends_at,
                    'status' => (string) $existingRow->status === 'active' ? 'recorded' : 'restricted',
                    'already_exists' => true,
                ];
            }

            $product = Product::query()
                ->whereKey($snapshot['product_id'])
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->where('status', 'active')
                ->where('is_public', true)
                ->where('purchase_enabled', true)
                ->where('licensing_enabled', true)
                ->whereIn('lifecycle', ['available', 'public-beta'])
                ->lockForUpdate()->first();

            $plan = Plan::query()
                ->whereKey($snapshot['plan_id'])
                ->where('product_id', $snapshot['product_id'])
                ->where('code', $snapshot['plan_code'])
                ->where('status', 'active')
                ->where('pricing_model', 'subscription')
                ->lockForUpdate()->first();

            $tier = self::PLAN_TO_TIER[$snapshot['plan_code']] ?? null;
            if (! $product instanceof Product
                || ! $plan instanceof Plan
                || $tier === null
                || (string) $plan->getAttribute('currency') !== $snapshot['currency']
                || (int) $plan->getAttribute('amount_minor') !== (int) $snapshot['amount_minor']
                || (string) $plan->getAttribute('billing_interval') !== $snapshot['billing_interval']
                || ! in_array($snapshot['billing_interval'], ['monthly', 'yearly'], true)) {
                throw new DomainException('OMNIDESK_COMMERCIAL_POLICY_NOT_APPROVED');
            }

            $requester = User::query()->whereKey((int) $orderRow->requester_user_id)->first();
            if (! $requester instanceof User || ! $requester->hasVerifiedEmail()
                || ! $this->capabilities->allows(
                    (int) $requester->getKey(),
                    $snapshot['organization_id'],
                    'commerce.purchase',
                )) {
                throw new DomainException('OMNIDESK_COMMERCIAL_REQUESTER_NOT_AUTHORIZED');
            }

            $policy = EntitlementPolicy::query()
                ->where('product_id', $snapshot['product_id'])
                ->where('code', self::POLICY_CODE)
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->lockForUpdate()->first();
            if (! $policy instanceof EntitlementPolicy) {
                throw new DomainException('OMNIDESK_PAID_ENTITLEMENT_POLICY_NOT_APPROVED');
            }

            // No policy for auto-converting a running Trial or replacing an
            // existing paid seat exists yet. Deny instead of double-issuing.
            if (DB::table('kslp_licenses')
                ->where('customer_id', $snapshot['organization_id'])
                ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
                ->where('status', 'active')
                ->whereNull('revoked_at')
                ->where('expires_at', '>', now())->exists()) {
                throw new DomainException('OMNIDESK_EXISTING_LICENSE_CONFLICT');
            }

            $now = now();
            $endsAt = $snapshot['billing_interval'] === 'monthly'
                ? $now->copy()->addMonthNoOverflow()
                : $now->copy()->addYearNoOverflow();
            $entitlement = $this->entitlements->issue(
                $snapshot['organization_id'],
                $policy,
                'omnidesk:paid-order:'.$orderId,
            );
            if ($entitlement->getAttribute('status') !== 'active'
                || $entitlement->getAttribute('ends_at') !== null
                || (string) $entitlement->getAttribute('organization_id') !== $snapshot['organization_id']) {
                throw new DomainException('OMNIDESK_PAID_ENTITLEMENT_CONFLICT');
            }
            $entitlement->forceFill([
                'starts_at' => $now,
                'ends_at' => $endsAt,
            ])->save();

            $licenseId = (string) Str::uuid();
            DB::table('kslp_licenses')->insert([
                'id' => $licenseId,
                'customer_id' => $snapshot['organization_id'],
                'product' => OmniDeskLicenseContract::PRODUCT_ID,
                'plan' => $tier,
                'status' => 'active',
                'trial_subject_hash' => null,
                'sequence' => 1,
                'starts_at' => $now,
                'expires_at' => $endsAt,
                'grace_until' => null,
                'revoked_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);
            DB::table('commerce_paid_fulfillments')->insert([
                'commercial_order_id' => $orderId,
                'organization_id' => $snapshot['organization_id'],
                'product_id' => $snapshot['product_id'],
                'plan_id' => $snapshot['plan_id'],
                'entitlement_id' => (string) $entitlement->getKey(),
                'license_id' => $licenseId,
                'provider' => 'razorpay',
                'provider_order_id' => $proof->providerOrderId,
                'payment_reference' => $paymentReference,
                'period_starts_at' => $now,
                'period_ends_at' => $endsAt,
                'status' => 'active',
                'created_at' => $now,
                'updated_at' => $now,
            ]);
            DB::table('kslp_license_events')->insert([
                'license_id' => $licenseId,
                'actor_id' => 'kmj-licensing-hub-settlement',
                'action' => 'omnidesk_paid_auto_fulfilled',
                'reason' => 'Independently verified live capture and immutable approved subscription period',
                'correlation_id' => (string) Str::uuid(),
                'metadata' => json_encode([
                    'commercial_order_id' => $orderId,
                    'entitlement_id' => (string) $entitlement->getKey(),
                    'provider' => 'razorpay',
                    'payment_reference_sha256' => hash('sha256', $paymentReference),
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
            ]);

            CommercialLedgerEntry::query()->create([
                'order_id' => $orderId,
                'organization_id' => $snapshot['organization_id'],
                'actor_user_id' => null,
                'event_type' => 'commerce.order.fulfilled',
                'payload' => [
                    'product_id' => $snapshot['product_id'],
                    'plan_id' => $snapshot['plan_id'],
                    'license_id' => $licenseId,
                    'entitlement_id' => (string) $entitlement->getKey(),
                    'status' => 'fulfilled',
                ],
                'occurred_at' => $now,
            ]);

            return [
                'commercial_order_id' => $orderId,
                'license_id' => $licenseId,
                'entitlement_id' => (string) $entitlement->getKey(),
                'expires_at' => $endsAt->toDateTimeString(),
                'status' => 'recorded',
                'already_exists' => false,
            ];
        }, 3);
    }

    private function assertVerifiedPayment(
        OmniDeskVerifiedLiveCapture $proof,
        object $link,
        string $paymentReference,
    ): void {
        /** @var array{provider_order_id:string,currency:string,amount_minor:int|string} $linkData */
        $linkData = (array) $link;

        if ($proof->provider !== 'razorpay'
            || $proof->providerOrderId !== (string) $linkData['provider_order_id']
            || $proof->paymentReference !== $paymentReference
            || $proof->environment !== 'live'
            || ! $proof->captured
            || $proof->refundedMinor !== 0
            || $proof->currency !== 'INR'
            || $proof->currency !== (string) $linkData['currency']
            || $proof->amountMinor !== (int) $linkData['amount_minor']) {
            throw new DomainException('OMNIDESK_PAYMENT_NOT_VERIFIED_LIVE');
        }
    }
}
