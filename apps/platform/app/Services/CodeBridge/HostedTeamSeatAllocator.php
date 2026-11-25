<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Internal source-only allocator. No public route, capacity writer, payment
 * activation or gateway dispatch is registered. Capacity must come from the
 * reviewed commercial fulfillment authority, never a client or price preview.
 */
final class HostedTeamSeatAllocator
{
    public function allocateTrusted(string $capacityId, string $membershipId): string
    {
        if (! Str::isUuid($capacityId) || ! Str::isUuid($membershipId)) {
            throw new DomainException('CODEBRIDGE_SEAT_INVALID_IDENTITY');
        }

        return DB::transaction(function () use ($capacityId, $membershipId): string {
            $now = now();
            $capacity = DB::table('codebridge_hosted_team_capacity')->where('id', $capacityId)
                ->whereNull('revoked_at')->where('starts_at', '<=', $now)->where('ends_at', '>', $now)
                ->lockForUpdate()->first();
            if ($capacity === null || (int) $capacity->seat_quantity < 3 || (int) $capacity->seat_quantity > 1000
                || (int) $capacity->total_minor < 1 || trim((string) $capacity->offer_version) === '') {
                throw new DomainException('CODEBRIDGE_SEAT_CAPACITY_REQUIRED');
            }

            $license = DB::table('kslp_licenses')->where('id', $capacity->license_id)
                ->where('product', 'KMJ_CODEBRIDGE')->where('plan', 'team')->where('status', 'active')
                ->whereNull('revoked_at')->where('starts_at', '<=', $now)->where('expires_at', '>', $now)
                ->lockForUpdate()->first();
            if ($license === null) {
                throw new DomainException('CODEBRIDGE_SEAT_LICENSE_REQUIRED');
            }

            $order = DB::table('commerce_orders')->where('id', $capacity->commercial_order_id)
                ->where('organization_id', $license->customer_id)->where('status', 'confirmed')
                ->whereNotNull('confirmed_at')->whereNull('cancelled_at')
                ->where('amount_minor', $capacity->total_minor)->where('currency', $capacity->currency)
                ->lockForUpdate()->first();
            if ($order === null || ! DB::table('products')->where('id', $order->product_id)
                ->where('slug', 'kmj-codebridge')->where('status', 'active')->exists()) {
                throw new DomainException('CODEBRIDGE_SEAT_ORDER_REQUIRED');
            }

            $entitlement = DB::table('entitlements')->where('id', $capacity->entitlement_id)
                ->where('organization_id', $license->customer_id)->where('product_id', $order->product_id)
                ->where('idempotency_key', 'commercial-order:'.$order->id)->where('status', 'active')
                ->where('starts_at', '<=', $now)
                ->where(fn ($query) => $query->whereNull('ends_at')->orWhere('ends_at', '>', $now))
                ->lockForUpdate()->first();
            if ($entitlement === null) {
                throw new DomainException('CODEBRIDGE_SEAT_FULFILLMENT_REQUIRED');
            }

            // The current reconciler is sandbox-only. A future live authority
            // must record matching captured-payment evidence before allocation.
            $liveLink = DB::table('commerce_provider_orders')->where('commercial_order_id', $order->id)
                ->where('provider', 'razorpay')->where('environment', 'live')
                ->where('amount_minor', $order->amount_minor)->where('currency', $order->currency)->first();
            if ($liveLink === null || ! DB::table('payment_webhook_events')
                ->where('provider', 'razorpay')->where('provider_order_id', $liveLink->provider_order_id)
                ->whereIn('event_type', ['payment.captured', 'order.paid'])
                ->where('processing_status', 'reconciled')->where('processing_note', 'CONFIRMED')
                ->whereNotNull('provider_payment_id')->get(['provider_payment_id'])
                ->contains(fn ($event): bool => 'razorpay:'.$event->provider_payment_id === $order->confirmation_reference)) {
                throw new DomainException('CODEBRIDGE_SEAT_LIVE_SETTLEMENT_REQUIRED');
            }

            $member = DB::table('organization_memberships')->where('id', $membershipId)
                ->where('organization_id', $license->customer_id)->whereIn('role', ['owner', 'admin', 'member'])
                ->lockForUpdate()->first();
            if ($member === null || ! DB::table('users')->where('id', $member->user_id)->whereNotNull('email_verified_at')->exists()) {
                throw new DomainException('CODEBRIDGE_SEAT_MEMBER_REQUIRED');
            }

            $existing = DB::table('codebridge_hosted_seat_assignments')->where('license_id', $license->id)
                ->where('membership_id', $membershipId)->lockForUpdate()->first();
            if ($existing !== null) {
                if ($existing->revoked_at !== null || (string) $existing->organization_id !== (string) $license->customer_id) {
                    throw new DomainException('CODEBRIDGE_SEAT_ASSIGNMENT_CONFLICT');
                }

                return (string) $existing->id;
            }

            // Serialize allocations on capacity/license rows. Revoked seats
            // consume capacity until a separately reviewed transfer policy.
            if (DB::table('codebridge_hosted_seat_assignments')->where('license_id', $license->id)->count() >= (int) $capacity->seat_quantity) {
                throw new DomainException('CODEBRIDGE_SEAT_CAPACITY_EXHAUSTED');
            }

            $id = (string) Str::uuid();
            DB::table('codebridge_hosted_seat_assignments')->insert([
                'id' => $id,
                'organization_id' => $license->customer_id,
                'membership_id' => $membershipId,
                'license_id' => $license->id,
                'assignment_revision' => 1,
                'starts_at' => $now,
                'ends_at' => min($capacity->ends_at, $license->expires_at),
                'created_at' => $now,
                'updated_at' => $now,
            ]);

            return $id;
        }, 3);
    }
}
