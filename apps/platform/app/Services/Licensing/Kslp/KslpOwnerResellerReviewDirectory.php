<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Owner-only, bounded grant directory. Candidate pairs are advisory; the
 * existing grant authority revalidates the issuer, product and membership
 * inside its transaction before granting anything.
 */
final class KslpOwnerResellerReviewDirectory
{
    public function __construct(private readonly PlatformOwnerAccess $ownerAccess) {}

    /** @return array{schema_ready: bool, grant_enabled: bool, candidates: list<array<string, string>>, grants: list<array<string, string|null>>, candidates_truncated: bool, grants_truncated: bool} */
    public function forOwner(User $owner): array
    {
        $this->ownerAccess->require($owner);

        if (! Schema::hasTable('kslp_reseller_review_grants')) {
            return [
                'schema_ready' => false,
                'grant_enabled' => false,
                'candidates' => [],
                'grants' => [],
                'candidates_truncated' => false,
                'grants_truncated' => false,
            ];
        }

        $now = now();
        $candidates = DB::table('kslp_licensed_products as product')
            ->join('kslp_issuer_subscriptions as issuer', 'issuer.organization_id', '=', 'product.organization_id')
            ->join('organization_memberships as membership', 'membership.organization_id', '=', 'product.organization_id')
            ->join('users as reviewer', 'reviewer.id', '=', 'membership.user_id')
            ->join('organizations as organization', 'organization.id', '=', 'product.organization_id')
            ->where('product.status', 'active')
            ->where('issuer.status', 'active')
            ->where(function ($query) use ($now): void {
                $query->whereNull('issuer.current_period_end')->orWhere('issuer.current_period_end', '>', $now);
            })
            ->where('membership.role', 'member')
            ->whereNotNull('reviewer.email_verified_at')
            ->whereNotExists(function ($query): void {
                $query->selectRaw('1')->from('kslp_reseller_review_grants as existing_grant')
                    ->whereColumn('existing_grant.issuer_organization_id', 'product.organization_id')
                    ->whereColumn('existing_grant.licensed_product_id', 'product.id')
                    ->whereColumn('existing_grant.reseller_user_id', 'reviewer.id');
            })
            ->orderBy('organization.name')->orderBy('product.name')->orderBy('product.id')->orderBy('reviewer.id')
            ->limit(101)
            ->get([
                'product.organization_id', 'organization.name as organization_name',
                'product.id as product_id', 'product.product_code', 'product.name as product_name',
                'reviewer.id as reseller_user_id', 'reviewer.name as reseller_name',
            ]);

        $grants = DB::table('kslp_reseller_review_grants as grant')
            ->join('organizations as organization', 'organization.id', '=', 'grant.issuer_organization_id')
            ->join('kslp_licensed_products as product', function ($join): void {
                $join->on('product.id', '=', 'grant.licensed_product_id')
                    ->on('product.organization_id', '=', 'grant.issuer_organization_id');
            })
            ->join('users as reviewer', 'reviewer.id', '=', 'grant.reseller_user_id')
            ->orderByDesc('grant.created_at')->orderBy('grant.id')
            ->limit(101)
            ->get([
                'grant.id', 'organization.name as organization_name',
                'product.product_code', 'product.name as product_name',
                'reviewer.name as reseller_name', 'grant.reseller_user_id',
                'grant.expires_at', 'grant.revoked_at',
            ]);

        return [
            'schema_ready' => true,
            'grant_enabled' => (bool) config('services.kmj_reseller_review.grant_enabled', false),
            'candidates' => array_values($candidates->take(100)->map(static function (object $record): array {
                $row = (array) $record;

                return [
                    'organization_id' => (string) $row['organization_id'],
                    'organization_name' => (string) $row['organization_name'],
                    'product_id' => (string) $row['product_id'],
                    'product_code' => (string) $row['product_code'],
                    'product_name' => (string) $row['product_name'],
                    'reseller_user_id' => (string) $row['reseller_user_id'],
                    'reseller_name' => (string) $row['reseller_name'],
                ];
            })->all()),
            'grants' => array_values($grants->take(100)->map(static function (object $record): array {
                $row = (array) $record;

                return [
                    'id' => (string) $row['id'],
                    'organization_name' => (string) $row['organization_name'],
                    'product_code' => (string) $row['product_code'],
                    'product_name' => (string) $row['product_name'],
                    'reseller_user_id' => (string) $row['reseller_user_id'],
                    'reseller_name' => (string) $row['reseller_name'],
                    'expires_at' => (string) $row['expires_at'],
                    'revoked_at' => $row['revoked_at'] === null ? null : (string) $row['revoked_at'],
                ];
            })->all()),
            'candidates_truncated' => $candidates->count() > 100,
            'grants_truncated' => $grants->count() > 100,
        ];
    }
}
