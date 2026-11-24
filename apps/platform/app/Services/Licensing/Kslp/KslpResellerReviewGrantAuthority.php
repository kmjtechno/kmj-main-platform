<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Carbon\CarbonImmutable;
use DateTimeInterface;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;

/**
 * Internal-only authorization foundation: review one product, never issue
 * licenses, manage the issuer, grant credits or redeem an order. No route or
 * customer-facing caller is registered by this slice. Any future mutation
 * route must enforce authentication, password confirmation and owner access.
 */
final class KslpResellerReviewGrantAuthority
{
    private const PERMISSION = 'funding_evidence_review';

    public function __construct(
        private readonly PlatformOwnerAccess $ownerAccess,
        private readonly OrganizationCapabilityContext $capabilities,
    ) {}

    /**
     * @return array<string, mixed>
     */
    public function grant(
        int $ownerId,
        string $organizationId,
        string $productId,
        int $resellerId,
        DateTimeInterface $expiresAt,
        string $reason,
    ): array {
        $this->requireOwner($ownerId);
        $reason = $this->validateReason($reason);
        $expiry = CarbonImmutable::instance($expiresAt)->utc();
        if ($expiry->lte(now()) || $expiry->gt(now()->addDays(90))) {
            throw new DomainException('KSLP_RESELLER_GRANT_EXPIRY_INVALID');
        }

        $this->requireSchema();

        return DB::transaction(function () use (
            $ownerId, $organizationId, $productId, $resellerId, $expiry, $reason,
        ): array {
            $this->requireOwner($ownerId);
            $this->lockActiveScope($organizationId, $productId);
            $membershipId = $this->eligibleMembership($resellerId, $organizationId);
            if ($membershipId === null) {
                throw new DomainException('KSLP_RESELLER_MEMBER_NOT_ELIGIBLE');
            }

            $query = DB::table('kslp_reseller_review_grants')
                ->where('issuer_organization_id', $organizationId)
                ->where('licensed_product_id', $productId)
                ->where('reseller_user_id', $resellerId);
            $existing = $query->lockForUpdate()->first();
            if ($existing !== null) {
                throw new DomainException('KSLP_RESELLER_GRANT_ALREADY_RECORDED');
            }

            $id = (string) Str::uuid();
            DB::table('kslp_reseller_review_grants')->insert([
                'id' => $id,
                'issuer_organization_id' => $organizationId,
                'licensed_product_id' => $productId,
                'reseller_user_id' => $resellerId,
                'membership_id' => $membershipId,
                'permission' => self::PERMISSION,
                'expires_at' => $expiry,
                'revoked_at' => null,
                'granted_by_user_id' => $ownerId,
                'created_at' => now(),
                'updated_at' => now(),
            ]);
            $this->audit($ownerId, $organizationId, $productId, $resellerId, $id, 'kslp_reseller_review_granted', $reason);

            return ['id' => $id, 'permission' => self::PERMISSION, 'paid_issuance_enabled' => false];
        }, 3);
    }

    public function revoke(
        int $ownerId,
        string $organizationId,
        string $productId,
        int $resellerId,
        string $reason,
    ): void {
        $this->requireOwner($ownerId);
        $reason = $this->validateReason($reason);
        $this->requireSchema();

        DB::transaction(function () use ($ownerId, $organizationId, $productId, $resellerId, $reason): void {
            $this->requireOwner($ownerId);
            // Revocation must work even if issuer, member or product is paused.
            $row = DB::table('kslp_reseller_review_grants')
                ->where('issuer_organization_id', $organizationId)
                ->where('licensed_product_id', $productId)
                ->where('reseller_user_id', $resellerId)
                ->lockForUpdate()->first();

            if ($row === null) {
                throw new DomainException('KSLP_RESELLER_GRANT_NOT_FOUND');
            }
            if ($row->revoked_at !== null) {
                return;
            }

            DB::table('kslp_reseller_review_grants')->where('id', $row->id)->update([
                'revoked_at' => now(),
                'updated_at' => now(),
            ]);
            $this->audit($ownerId, $organizationId, $productId, $resellerId, (string) $row->id, 'kslp_reseller_review_revoked', $reason);
        }, 3);
    }

    public function allowsReview(int $userId, string $organizationId, string $productId): bool
    {
        if (! Schema::hasTable('kslp_reseller_review_grants')) {
            return false;
        }

        $membershipId = $this->eligibleMembership($userId, $organizationId);
        if ($membershipId === null) {
            return false;
        }

        return DB::table('kslp_reseller_review_grants as grant')
            ->join('kslp_licensed_products as product', 'product.id', '=', 'grant.licensed_product_id')
            ->join('kslp_issuer_subscriptions as issuer', 'issuer.organization_id', '=', 'grant.issuer_organization_id')
            ->where('grant.issuer_organization_id', $organizationId)
            ->where('grant.licensed_product_id', $productId)
            ->where('grant.reseller_user_id', $userId)
            ->where('grant.membership_id', $membershipId)
            ->where('grant.permission', self::PERMISSION)
            ->whereNull('grant.revoked_at')
            ->where('grant.expires_at', '>', now())
            ->where('product.organization_id', $organizationId)
            ->where('product.status', 'active')
            ->where('issuer.status', 'active')
            ->where(function ($query): void {
                $query->whereNull('issuer.current_period_end')->orWhere('issuer.current_period_end', '>', now());
            })->exists();
    }

    /**
     * Read only the member's currently authorized products and aggregate
     * pending evidence. Match membership, user, issuer and product in the
     * same SQL statement; never widen this to the issuer's other products.
     *
     * @return array{products: list<array{id: string, name: string, product_code: string, expires_at: string, pending_evidence_count: int|null}>, truncated: bool}
     */
    public function reviewWorkspace(int $userId): array
    {
        if ($userId < 1 || ! Schema::hasTable('kslp_reseller_review_grants')) {
            return ['products' => [], 'truncated' => false];
        }

        $now = now();
        $query = DB::table('kslp_reseller_review_grants as grant')
            ->join('organization_memberships as membership', function ($join): void {
                $join->on('membership.id', '=', 'grant.membership_id')
                    ->on('membership.organization_id', '=', 'grant.issuer_organization_id')
                    ->on('membership.user_id', '=', 'grant.reseller_user_id');
            })
            ->join('users as reviewer', 'reviewer.id', '=', 'grant.reseller_user_id')
            ->join('kslp_licensed_products as product', function ($join): void {
                $join->on('product.id', '=', 'grant.licensed_product_id')
                    ->on('product.organization_id', '=', 'grant.issuer_organization_id');
            })
            ->join('kslp_issuer_subscriptions as issuer', 'issuer.organization_id', '=', 'grant.issuer_organization_id')
            ->where('grant.reseller_user_id', $userId)
            ->where('membership.role', 'member')
            ->whereNotNull('reviewer.email_verified_at')
            ->where('grant.permission', self::PERMISSION)
            ->whereNull('grant.revoked_at')
            ->where('grant.expires_at', '>', $now)
            ->where('product.status', 'active')
            ->where('issuer.status', 'active')
            ->where(function ($query) use ($now): void {
                $query->whereNull('issuer.current_period_end')->orWhere('issuer.current_period_end', '>', $now);
            })
            ->select(['product.id', 'product.name', 'product.product_code', 'grant.expires_at']);

        if (Schema::hasTable('kslp_reseller_credit_ledger')) {
            $query->selectSub(
                DB::table('kslp_reseller_credit_ledger as evidence')
                    ->selectRaw('COUNT(*)')
                    ->whereColumn('evidence.issuer_organization_id', 'grant.issuer_organization_id')
                    ->whereColumn('evidence.licensed_product_id', 'grant.licensed_product_id')
                    ->where('evidence.event_type', 'evidence_pending')
                    ->where('evidence.evidence_state', 'unverified')
                    ->where('evidence.credits_delta', 0),
                'pending_evidence_count'
            );
        } else {
            $query->selectRaw('NULL AS pending_evidence_count');
        }

        $rows = $query->orderBy('product.name')->orderBy('product.id')->limit(51)->get();
        $products = $rows->take(50)->map(static function (object $record): array {
            $row = (array) $record;

            return [
                'id' => (string) $row['id'],
                'name' => (string) $row['name'],
                'product_code' => (string) $row['product_code'],
                'expires_at' => (string) $row['expires_at'],
                'pending_evidence_count' => $row['pending_evidence_count'] === null
                    ? null : (int) $row['pending_evidence_count'],
            ];
        })->values()->all();

        return ['products' => array_values($products), 'truncated' => $rows->count() > 50];
    }

    private function requireOwner(int $ownerId): void
    {
        $owner = User::query()->find($ownerId);
        if ($owner === null || ! $this->ownerAccess->allows($owner)) {
            throw new DomainException('KSLP_RESELLER_GRANT_OWNER_REQUIRED');
        }
    }

    private function validateReason(string $reason): string
    {
        $reason = trim($reason);
        if (mb_strlen($reason) < 8 || mb_strlen($reason) > 240) {
            throw new DomainException('KSLP_RESELLER_GRANT_REASON_REQUIRED');
        }

        return $reason;
    }

    private function requireSchema(): void
    {
        if (! Schema::hasTable('kslp_reseller_review_grants')) {
            throw new DomainException('KSLP_RESELLER_GRANT_SCHEMA_NOT_READY');
        }
    }

    private function eligibleMembership(int $userId, string $organizationId): ?string
    {
        $user = User::query()->find($userId);
        $membership = $this->capabilities->membershipFor($userId, $organizationId);
        // A delegated reviewer is an explicitly selected verified member,
        // not an organization admin or platform owner by inference.
        if ($user === null || ! $user->hasVerifiedEmail() || $membership === null
            || $membership->getAttribute('role') !== 'member') {
            return null;
        }

        return (string) $membership->getKey();
    }

    private function lockActiveScope(string $organizationId, string $productId): void
    {
        $issuer = DB::table('kslp_issuer_subscriptions')
            ->where('organization_id', $organizationId)->lockForUpdate()->first();
        if ($issuer === null || $issuer->status !== 'active'
            || ($issuer->current_period_end !== null
                && CarbonImmutable::parse((string) $issuer->current_period_end)->lte(now()))) {
            throw new DomainException('KSLP_RESELLER_ISSUER_INACTIVE');
        }
        $product = DB::table('kslp_licensed_products')
            ->where('organization_id', $organizationId)->where('id', $productId)->lockForUpdate()->first();
        if ($product === null || $product->status !== 'active') {
            throw new DomainException('KSLP_RESELLER_PRODUCT_NOT_AUTHORIZED');
        }
    }

    private function audit(
        int $ownerId,
        string $organizationId,
        string $productId,
        int $resellerId,
        string $grantId,
        string $action,
        string $reason,
    ): void {
        DB::table('license_audit_events')->insert([
            'actor_id' => $ownerId,
            'organization_id' => $organizationId,
            'action' => $action,
            'status' => 'success',
            'metadata' => json_encode([
                'grant_id' => $grantId,
                'licensed_product_id' => $productId,
                'reseller_user_id' => $resellerId,
                'permission' => self::PERMISSION,
                'reason' => $reason,
            ], JSON_THROW_ON_ERROR),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }
}
