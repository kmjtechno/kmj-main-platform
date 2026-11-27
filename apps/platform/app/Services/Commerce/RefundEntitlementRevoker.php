<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\Staff\PlatformStaffAuthority;
use DomainException;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Services\EntitlementRevoker;

/**
 * Explicit owner action: after a refund was recorded for an order, revoke the access that order
 * gave (the active entitlements of the same organization and product). Never automatic, never
 * implied by a refund record, and refused while the organization still has another paid, unrefunded
 * order for the same product. A refund does not move money here; revocation is its own audited step.
 */
final class RefundEntitlementRevoker
{
    public function __construct(
        private readonly PlatformStaffAuthority $authority,
        private readonly EntitlementRevoker $revoker,
    ) {}

    /** @return array{order_id: string, revoked: int, already_revoked: int} */
    public function revoke(int $actorUserId, string $orderId): array
    {
        $actor = User::query()->find($actorUserId);
        if (! $actor instanceof User || ! $this->authority->allows($actor, PlatformStaffAuthority::ENTITLEMENT_REVOKE_AFTER_REFUND)) {
            throw new DomainException('REFUND_REVOKE_NOT_AUTHORIZED');
        }

        $order = DB::table('commerce_orders')->where('id', $orderId)->first();
        if ($order === null) {
            throw new DomainException('REFUND_REVOKE_ORDER_NOT_FOUND');
        }
        if (! DB::table('commerce_order_refund_records')->where('order_id', $orderId)->exists()) {
            throw new DomainException('REFUND_REVOKE_REFUND_RECORD_REQUIRED');
        }

        $otherPaid = DB::table('commerce_orders as o')
            ->where('o.organization_id', $order->organization_id)
            ->where('o.product_id', $order->product_id)
            ->where('o.status', 'confirmed')
            ->where('o.id', '!=', $orderId)
            ->whereNotExists(static function ($query): void {
                $query->select(DB::raw(1))->from('commerce_order_refund_records as r')
                    ->whereColumn('r.order_id', 'o.id');
            })
            ->exists();
        if ($otherPaid) {
            throw new DomainException('REFUND_REVOKE_OTHER_PAID_ORDER_EXISTS');
        }

        $active = Entitlement::query()
            ->where('organization_id', $order->organization_id)
            ->where('product_id', $order->product_id)
            ->where('status', 'active')
            ->pluck('id');
        if ($active->isEmpty()) {
            $already = Entitlement::query()
                ->where('organization_id', $order->organization_id)
                ->where('product_id', $order->product_id)
                ->where('status', 'revoked')
                ->count();
            if ($already > 0) {
                return ['order_id' => $orderId, 'revoked' => 0, 'already_revoked' => $already];
            }
            throw new DomainException('REFUND_REVOKE_NO_ACTIVE_ENTITLEMENT');
        }

        foreach ($active as $entitlementId) {
            $this->revoker->revoke((string) $entitlementId);
        }

        OperatorActionAudit::query()->create([
            'actor_user_id' => $actorUserId,
            'action' => 'order.refund.entitlement_revoke',
            'outcome' => 'revoked',
            'metadata' => [
                'order_id' => $orderId,
                'organization_id' => (string) $order->organization_id,
                'product_id' => (string) $order->product_id,
                'entitlements_revoked' => $active->count(),
            ],
        ]);

        return ['order_id' => $orderId, 'revoked' => $active->count(), 'already_revoked' => 0];
    }
}
