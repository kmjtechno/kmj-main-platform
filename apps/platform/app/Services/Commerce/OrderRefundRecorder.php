<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\Staff\PlatformStaffAuthority;
use DomainException;
use Illuminate\Support\Facades\DB;

/**
 * Records a refund the platform owner already made in the payment provider's dashboard.
 * Append-only. It never calls a provider, never moves money, and never changes an order's
 * status or any license/entitlement (payment state is not a license; revocation is a
 * separate explicit owner action). Partial refunds are allowed up to the confirmed amount.
 */
final class OrderRefundRecorder
{
    public function __construct(private readonly PlatformStaffAuthority $authority) {}

    /**
     * @return array{id:int,order_id:string,amount_minor:int,refunded_total_minor:int,reused:bool}
     */
    public function record(
        int $actorUserId,
        string $orderId,
        int $amountMinor,
        string $reason,
        string $requestKey,
        ?string $providerRefundReference = null,
    ): array {
        $actor = User::query()->find($actorUserId);
        if (! $actor instanceof User || ! $this->authority->allows($actor, PlatformStaffAuthority::BILLING_REFUND_RECORD)) {
            throw new DomainException('REFUND_RECORD_NOT_AUTHORIZED');
        }

        $requestKey = trim($requestKey);
        if (preg_match('/\A[A-Za-z0-9._:-]{8,120}\z/D', $requestKey) !== 1) {
            throw new DomainException('REFUND_RECORD_KEY_INVALID');
        }
        $reason = trim($reason);
        if ($reason === '' || mb_strlen($reason) > 240) {
            throw new DomainException('REFUND_RECORD_REASON_INVALID');
        }
        $providerRefundReference = $providerRefundReference === null ? null : trim($providerRefundReference);
        if ($providerRefundReference !== null
            && preg_match('/\A[A-Za-z0-9._:-]{1,120}\z/D', $providerRefundReference) !== 1) {
            throw new DomainException('REFUND_RECORD_REFERENCE_INVALID');
        }
        if ($amountMinor < 1) {
            throw new DomainException('REFUND_RECORD_AMOUNT_INVALID');
        }

        return DB::transaction(function () use ($actorUserId, $orderId, $amountMinor, $reason, $requestKey, $providerRefundReference): array {
            $order = DB::table('commerce_orders')->where('id', $orderId)->lockForUpdate()->first();
            if ($order === null) {
                throw new DomainException('REFUND_RECORD_ORDER_NOT_FOUND');
            }
            if ($order->status !== 'confirmed' || $order->amount_minor === null || $order->currency === null) {
                throw new DomainException('REFUND_RECORD_ORDER_NOT_CONFIRMED');
            }

            $existing = DB::table('commerce_order_refund_records')->where('request_key', $requestKey)->first();
            $already = (int) DB::table('commerce_order_refund_records')->where('order_id', $orderId)->sum('amount_minor');
            if ($existing !== null) {
                if ($existing->order_id !== $orderId || (int) $existing->amount_minor !== $amountMinor) {
                    throw new DomainException('REFUND_RECORD_KEY_REUSED');
                }

                return [
                    'id' => (int) $existing->id,
                    'order_id' => $orderId,
                    'amount_minor' => $amountMinor,
                    'refunded_total_minor' => $already,
                    'reused' => true,
                ];
            }

            if ($already + $amountMinor > (int) $order->amount_minor) {
                throw new DomainException('REFUND_RECORD_EXCEEDS_CONFIRMED_AMOUNT');
            }

            $id = DB::table('commerce_order_refund_records')->insertGetId([
                'order_id' => $orderId,
                'organization_id' => $order->organization_id,
                'amount_minor' => $amountMinor,
                'currency' => $order->currency,
                'provider_refund_reference' => $providerRefundReference,
                'reason' => $reason,
                'recorded_by_user_id' => $actorUserId,
                'request_key' => $requestKey,
                'recorded_at' => now(),
            ]);

            OperatorActionAudit::query()->create([
                'actor_user_id' => $actorUserId,
                'action' => 'order.refund.record',
                'outcome' => 'recorded',
                'metadata' => [
                    'order_id' => $orderId,
                    'amount_minor' => $amountMinor,
                    'currency' => $order->currency,
                    'refunded_total_minor' => $already + $amountMinor,
                ],
            ]);

            return [
                'id' => (int) $id,
                'order_id' => $orderId,
                'amount_minor' => $amountMinor,
                'refunded_total_minor' => $already + $amountMinor,
                'reused' => false,
            ];
        });
    }
}
