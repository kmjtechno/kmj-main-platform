<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Customer-safe KSLP records, not issuance or a new licensing authority.
 *
 * The same commercial KSLP tables power the owner Hub. An unverified or
 * unrelated actor cannot select a customer/tenant by query string; the only
 * authorized scope comes from the authenticated user and current memberships.
 */
final class KslpCustomerWorkspaceQuery
{
    public function __construct(private readonly OrganizationDirectory $organizations) {}

    /** @return array<string, mixed> */
    public function forUser(User $actor): array
    {
        $userId = (int) $actor->getKey();
        $organizationNames = [];
        foreach ($this->organizations->forUser($userId) as $organization) {
            if (! is_array($organization)
                || ! is_string($organization['id'] ?? null)
                || ! is_string($organization['name'] ?? null)) {
                continue;
            }
            $organizationNames[$organization['id']] = $organization['name'];
        }

        $customerIds = array_values(array_unique([
            (string) $userId,
            ...array_keys($organizationNames),
        ]));
        $query = DB::table('kslp_licenses')->whereIn('customer_id', $customerIds);
        $total = (clone $query)->count();
        $now = Carbon::now();

        // Aggregate only. Server identities, device public keys, HWID hashes,
        // idempotency keys and plaintext bootstrap keys never enter Inertia.
        $licenses = $query->orderByDesc('created_at')->limit(100)
            ->get([
                'id', 'customer_id', 'product', 'plan', 'status',
                'starts_at', 'expires_at', 'grace_until', 'revoked_at',
            ]);
        $licenseIds = $licenses->pluck('id')->all();
        $bindings = $licenseIds === [] ? collect() : DB::table('kslp_activations')
            ->whereIn('license_id', $licenseIds)
            ->select('license_id')
            ->selectRaw('COUNT(*) AS recorded_count')
            ->selectRaw('SUM(CASE WHEN deactivated_at IS NULL THEN 1 ELSE 0 END) AS non_deactivated_count')
            ->selectRaw('MAX(activated_at) AS last_activated_at')
            ->groupBy('license_id')
            ->get()->keyBy('license_id');

        $safeLicenses = $licenses->map(function ($license) use ($organizationNames, $bindings, $now): array {
            $current = $bindings->get($license->id);
            $subject = (string) $license->customer_id;

            return [
                'id' => (string) $license->id,
                'product' => (string) $license->product,
                'plan' => (string) $license->plan,
                'state' => self::state($license, $now),
                'subject_label' => $organizationNames[$subject] ?? 'Personal license',
                'starts_at' => $license->starts_at,
                'expires_at' => $license->expires_at,
                'grace_until' => $license->grace_until,
                'recorded_devices' => (int) ($current->recorded_count ?? 0),
                'non_deactivated_devices' => (int) ($current->non_deactivated_count ?? 0),
                'last_activation_at' => $current->last_activated_at ?? null,
                // Absence of online heartbeat cannot be treated as connected.
                'online_status' => 'not_verified',
                'device_recovery_available' => false,
                'signed_download_verified' => false,
            ];
        })->all();

        $entitlements = $organizationNames === [] ? [] :
            DB::table('entitlements as e')
                ->join('products as p', 'p.id', '=', 'e.product_id')
                ->whereIn('e.organization_id', array_keys($organizationNames))
                ->orderByDesc('e.created_at')
                ->limit(100)
                ->get([
                    'e.id', 'e.organization_id', 'e.capability', 'e.status',
                    'e.starts_at', 'e.ends_at', 'p.name as product_name',
                    'p.slug as product_slug',
                ])->map(function ($entitlement) use ($organizationNames): array {
                    return [
                        'id' => (string) $entitlement->id,
                        'organization_name' => $organizationNames[(string) $entitlement->organization_id],
                        'product_name' => (string) $entitlement->product_name,
                        'product_slug' => (string) $entitlement->product_slug,
                        'capability' => (string) $entitlement->capability,
                        'status' => (string) $entitlement->status,
                        'starts_at' => $entitlement->starts_at,
                        'ends_at' => $entitlement->ends_at,
                        'signed_license_issued' => false,
                    ];
                })->all();

        return [
            'licenses' => $safeLicenses,
            'license_count' => $total,
            'licenses_truncated' => $total > count($safeLicenses),
            'product_entitlements' => $entitlements,
            'organizations' => array_values(array_map(
                fn (string $id, string $name): array => ['id' => $id, 'name' => $name],
                array_keys($organizationNames),
                array_values($organizationNames),
            )),
            'authorization_source' => 'authenticated_verified_membership',
            'device_reset_enabled' => false,
            'paid_issuance_enabled' => false,
            'trusted_download_source' => '/dashboard',
        ];
    }

    public static function state(object $license, Carbon $now): string
    {
        if ($license->revoked_at !== null) {
            return 'REVOKED';
        }
        if ($license->status !== 'active') {
            return 'RESTRICTED';
        }
        if ($now->lt(Carbon::parse($license->starts_at))) {
            return 'NOT_STARTED';
        }
        if ($now->lt(Carbon::parse($license->expires_at))) {
            return $now->copy()->addDays(7)->gte(Carbon::parse($license->expires_at))
                ? 'RENEWAL_DUE' : 'ACTIVE';
        }
        if ($license->grace_until !== null && $now->lt(Carbon::parse($license->grace_until))) {
            return 'GRACE';
        }

        return 'RESTRICTED';
    }
}
