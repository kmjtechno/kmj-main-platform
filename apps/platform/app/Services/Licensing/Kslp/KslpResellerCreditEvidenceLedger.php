<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

/**
 * Append-only, zero-credit evidence queue for a future governed reseller
 * program. No active reseller grant, wallet, payment proof, or license is
 * created by this service. Production credit funding remains unimplemented.
 */
final class KslpResellerCreditEvidenceLedger
{
    public function __construct(private readonly OrganizationCapabilityContext $capabilities) {}

    /**
     * @return array<string, mixed>
     */
    public function queuePending(
        int $actorUserId,
        string $issuerOrganizationId,
        string $licensedProductId,
        string $commercialOrderId,
        string $requestKey,
    ): array {
        $this->requireManageCapability($actorUserId, $issuerOrganizationId);

        $requestKey = trim($requestKey);
        if (preg_match('/\A[A-Za-z0-9._:-]{8,120}\z/D', $requestKey) !== 1) {
            throw new DomainException('KSLP_RESELLER_EVIDENCE_KEY_INVALID');
        }

        if (! Schema::hasTable('kslp_reseller_credit_ledger')) {
            throw new DomainException('KSLP_RESELLER_LEDGER_NOT_READY');
        }

        $eventHash = hash('sha256', 'kslp-reseller-evidence-v1|'.$requestKey);

        return DB::transaction(function () use (
            $actorUserId,
            $issuerOrganizationId,
            $licensedProductId,
            $commercialOrderId,
            $eventHash,
        ): array {
            $product = DB::table('kslp_licensed_products')
                ->where('organization_id', $issuerOrganizationId)
                ->where('id', $licensedProductId)
                ->first(['id']);

            $order = DB::table('commerce_orders')
                ->where('organization_id', $issuerOrganizationId)
                ->where('id', $commercialOrderId)
                ->first(['id', 'status']);

            if ($product === null || $order === null) {
                throw new DomainException('KSLP_RESELLER_EVIDENCE_SCOPE_INVALID');
            }

            $existing = DB::table('kslp_reseller_credit_ledger')
                ->where('event_key_hash', $eventHash)
                ->first();
            if ($existing !== null) {
                $this->assertSamePending($existing, $issuerOrganizationId, $licensedProductId, $commercialOrderId);

                return (array) $existing;
            }

            if (! in_array($order->status, ['requested', 'confirmed'], true)) {
                throw new DomainException('KSLP_RESELLER_ORDER_NOT_ELIGIBLE_FOR_REVIEW');
            }

            // The same globally unique event key cannot be repurposed, and
            // simultaneous distinct keys for one order/product must not
            // produce duplicate pending ledger rows.
            DB::table('kslp_reseller_credit_ledger')->insertOrIgnore([
                'issuer_organization_id' => $issuerOrganizationId,
                'licensed_product_id' => $licensedProductId,
                'commercial_order_id' => $commercialOrderId,
                'event_key_hash' => $eventHash,
                'event_type' => 'evidence_pending',
                'credits_delta' => 0,
                'evidence_state' => 'unverified',
                'actor_user_id' => $actorUserId,
                'created_at' => now(),
            ]);

            $record = DB::table('kslp_reseller_credit_ledger')
                ->where('event_key_hash', $eventHash)
                ->first();

            if ($record === null) {
                throw new DomainException('KSLP_RESELLER_ORDER_ALREADY_QUEUED');
            }

            $this->assertSamePending($record, $issuerOrganizationId, $licensedProductId, $commercialOrderId);

            return (array) $record;
        }, 3);
    }

    /**
     * Show only non-financial evidence counts. No spendable balance may be
     * inferred from pending orders or manually confirmed commerce orders.
     *
     * @return array{status: string, pending_evidence_count: int, available_credits: null, paid_issuance_enabled: false}
     */
    public function snapshotForActor(int $actorUserId, string $issuerOrganizationId): array
    {
        $this->requireManageCapability($actorUserId, $issuerOrganizationId);

        if (! Schema::hasTable('kslp_reseller_credit_ledger')) {
            return [
                'status' => 'schema_not_ready',
                'pending_evidence_count' => 0,
                'available_credits' => null,
                'paid_issuance_enabled' => false,
            ];
        }

        $pending = DB::table('kslp_reseller_credit_ledger')
            ->where('issuer_organization_id', $issuerOrganizationId)
            ->where('event_type', 'evidence_pending')
            ->where('evidence_state', 'unverified')
            ->count();

        return [
            'status' => 'funding_not_activated',
            'pending_evidence_count' => $pending,
            'available_credits' => null,
            'paid_issuance_enabled' => false,
        ];
    }

    private function requireManageCapability(int $actorUserId, string $issuerOrganizationId): void
    {
        if ($actorUserId < 1 || ! $this->capabilities->allows(
            $actorUserId, $issuerOrganizationId, 'license.manage'
        )) {
            throw new DomainException('KSLP_RESELLER_EVIDENCE_ACCESS_DENIED');
        }
    }

    private function assertSamePending(
        object $record,
        string $issuerOrganizationId,
        string $licensedProductId,
        string $commercialOrderId,
    ): void {
        // Illuminate's query builder returns a generic object; normalize it
        // before inspecting fixed ledger columns, including under PHPStan.
        $row = (array) $record;
        if (($row['issuer_organization_id'] ?? null) !== $issuerOrganizationId
            || ($row['licensed_product_id'] ?? null) !== $licensedProductId
            || ($row['commercial_order_id'] ?? null) !== $commercialOrderId
            || ($row['event_type'] ?? null) !== 'evidence_pending'
            || (int) ($row['credits_delta'] ?? -1) !== 0
            || ($row['evidence_state'] ?? null) !== 'unverified') {
            throw new DomainException('KSLP_RESELLER_EVIDENCE_IDEMPOTENCY_CONFLICT');
        }
    }
}
