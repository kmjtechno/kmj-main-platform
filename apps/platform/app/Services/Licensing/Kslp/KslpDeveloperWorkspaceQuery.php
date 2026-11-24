<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * One KSLP data authority for both the owner Licensing Hub and the tenant
 * developer workspace. Never turn a commercial lease into an issuer quota.
 */
final class KslpDeveloperWorkspaceQuery
{
    public function __construct(
        private readonly OrganizationDirectory $directory,
        private readonly OrganizationCapabilityContext $capabilities,
    ) {}

    /** @return array{organizations: array<int, array<string, mixed>>, applications: array<int, object>, keys: array<int, object>, canIssueKeys: bool} */
    public function forUser(User $actor): array
    {
        $organizations = collect($this->directory->forUser($actor->id))
            ->filter(fn (array $org): bool => $this->capabilities->allows($actor->id, $org['id'], 'license.manage'))
            ->map(function (array $org): array {
                $subscription = DB::table('kslp_issuer_subscriptions')
                    ->where('organization_id', $org['id'])->first();
                if ($subscription === null) {
                    $org['issuer_status'] = 'not_subscribed';
                    $org['product_limit'] = 0;
                    $org['monthly_issue_limit'] = null;
                    $org['current_period_end'] = null;
                } else {
                    $org['issuer_status'] = (string) $subscription->status;
                    if ($org['issuer_status'] === 'active'
                        && $subscription->current_period_end !== null
                        && now()->greaterThanOrEqualTo($subscription->current_period_end)) {
                        $org['issuer_status'] = 'expired';
                    }
                    $org['product_limit'] = (int) $subscription->product_limit;
                    $org['monthly_issue_limit'] = (int) $subscription->monthly_issue_limit;
                    $org['current_period_end'] = $subscription->current_period_end;
                }

                return $org;
            })->values()->all();

        $tenantIds = array_column($organizations, 'id');

        // These read-only aggregates use the same issuer monthly
        // server-clock window as KslpLicenseControlPlane::issueDelegated().
        // They are advisory snapshots, never spendable reseller credits or
        // proof that a payment or product release has been authorized.
        $productCounts = $tenantIds === [] ? collect() : DB::table('kslp_licensed_products')
            ->whereIn('organization_id', $tenantIds)
            ->select('organization_id')
            ->selectRaw('COUNT(*) AS total')
            ->groupBy('organization_id')
            ->pluck('total', 'organization_id');
        $issuedCounts = $tenantIds === [] ? collect() : DB::table('kslp_licenses')
            ->whereIn('issuer_organization_id', $tenantIds)
            ->where('created_at', '>=', now()->startOfMonth())
            ->select('issuer_organization_id')
            ->selectRaw('COUNT(*) AS total')
            ->groupBy('issuer_organization_id')
            ->pluck('total', 'issuer_organization_id');

        foreach ($organizations as &$organization) {
            $registered = (int) ($productCounts[$organization['id']] ?? 0);
            $issued = (int) ($issuedCounts[$organization['id']] ?? 0);
            $active = $organization['issuer_status'] === 'active';
            $monthlyLimit = $organization['monthly_issue_limit'];

            $organization['registered_products'] = $registered;
            $organization['monthly_issued'] = $issued;
            $organization['product_remaining'] = $active
                ? max(0, $organization['product_limit'] - $registered) : null;
            $organization['monthly_remaining'] = $active && $monthlyLimit !== null
                ? max(0, $monthlyLimit - $issued) : null;
        }
        unset($organization);

        $products = $tenantIds === [] ? [] : DB::table('kslp_licensed_products')
            ->whereIn('organization_id', $tenantIds)
            ->orderBy('created_at', 'desc')
            ->limit(100)
            ->get(['id', 'organization_id', 'product_code', 'name', 'status', 'created_at'])
            ->all();

        // Product-bound reseller evidence preview. Revalidate the exact
        // product/issuer pair in SQL; a mismatched historical ledger row
        // must not count toward another tenant's product. Missing migration
        // is unknown evidence, not a real zero balance.
        $evidenceReady = Schema::hasTable('kslp_reseller_credit_ledger');
        $productIds = array_map(static fn (object $product): string => (string) ((array) $product)['id'], $products);
        $pendingEvidence = ($evidenceReady && $productIds !== [])
            ? DB::table('kslp_reseller_credit_ledger as evidence')
                ->join('kslp_licensed_products as product', function ($join): void {
                    $join->on('product.id', '=', 'evidence.licensed_product_id')
                        ->on('product.organization_id', '=', 'evidence.issuer_organization_id');
                })
                ->whereIn('product.organization_id', $tenantIds)
                ->whereIn('product.id', $productIds)
                ->where('evidence.event_type', 'evidence_pending')
                ->where('evidence.evidence_state', 'unverified')
                ->where('evidence.credits_delta', 0)
                ->select('product.id')
                ->selectRaw('COUNT(*) AS total')
                ->groupBy('product.id')
                ->pluck('total', 'product.id')
            : collect();

        $products = array_map(static function (object $product) use ($evidenceReady, $pendingEvidence): object {
            $row = (array) $product;
            $row['pending_reseller_evidence_count'] = $evidenceReady
                ? (int) ($pendingEvidence[$row['id']] ?? 0)
                : null;

            return (object) $row;
        }, $products);

        // Read-only, aggregate-only device evidence. Never expose device
        // public keys, hardware hashes or idempotency tokens through Inertia.
        // A non-deactivated binding is NOT a live connection, entitlement or
        // proof that an expired/revoked license is usable.
        $bindingCounts = DB::table('kslp_activations')
            ->select('license_id')
            ->selectRaw('COUNT(*) AS recorded_binding_count')
            ->selectRaw('SUM(CASE WHEN deactivated_at IS NULL THEN 1 ELSE 0 END) AS non_deactivated_binding_count')
            ->selectRaw('MAX(activated_at) AS last_activation_at')
            ->groupBy('license_id');

        $storageReady = Schema::hasTable('kslp_license_keys');
        $keys = ($storageReady && $tenantIds !== [])
            ? DB::table('kslp_license_keys as k')
                ->join('kslp_licenses as l', 'l.id', '=', 'k.license_id')
                ->leftJoinSub($bindingCounts, 'bindings', fn ($join) => $join->on('bindings.license_id', '=', 'l.id'))
                ->whereIn('k.organization_id', $tenantIds)
                ->orderBy('k.created_at', 'desc')
                ->limit(100)
                ->get([
                    'k.id', 'k.organization_id', 'k.licensed_product_id',
                    'k.license_id', 'k.display_prefix', 'k.first_activated_at',
                    'k.revoked_at', 'l.plan', 'l.customer_id', 'l.expires_at',
                    'bindings.last_activation_at',
                    DB::raw('COALESCE(bindings.recorded_binding_count, 0) AS recorded_binding_count'),
                    DB::raw('COALESCE(bindings.non_deactivated_binding_count, 0) AS non_deactivated_binding_count'),
                ])->all() : [];

        return [
            'organizations' => $organizations,
            'applications' => $products,
            'keys' => $keys,
            'canIssueKeys' => $storageReady
                && (bool) config('services.kmj_developer_licensing.enabled', false),
        ];
    }
}
