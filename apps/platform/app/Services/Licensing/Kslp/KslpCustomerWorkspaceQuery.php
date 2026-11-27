<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use App\Models\User;
use App\Services\CodeBridge\HostedUsagePreview;
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
    public function __construct(
        private readonly OrganizationDirectory $organizations,
        private readonly HostedUsagePreview $usagePreview,
    ) {}

    /** @return array<string, mixed> */
    public function forUser(User $actor): array
    {
        $userId = (int) $actor->getKey();
        $organizationNames = $this->organizationNames($userId);

        ['licenses' => $safeLicenses, 'total' => $total] = $this->licenseRecords($userId, $organizationNames);

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
                        'status' => $entitlement->status === 'active' && $entitlement->ends_at !== null && Carbon::parse($entitlement->ends_at)->isPast()
                            ? 'expired'
                            : (string) $entitlement->status,
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
            'organizations' => array_map(
                fn (string $id, string $name): array => ['id' => $id, 'name' => $name],
                array_keys($organizationNames),
                array_values($organizationNames),
            ),
            'authorization_source' => 'authenticated_verified_membership',
            'device_reset_enabled' => false,
            'paid_issuance_enabled' => false,
            'trusted_download_source' => '/dashboard',
            // All users see the same non-billable proposal. No unverified
            // seat/tenant counters or live payment assertions are exposed.
            'codebridge_usage_preview' => $this->usagePreview->catalog(),
        ];
    }

    /**
     * The same customer-scoped license records the Licensing page shows, so the
     * dashboard can never report "nothing" while a license exists.
     *
     * @return array{licenses: array<int, array<string, mixed>>, total: int}
     */
    public function licensesForUser(User $actor): array
    {
        $userId = (int) $actor->getKey();

        return $this->licenseRecords($userId, $this->organizationNames($userId));
    }

    /** @return array<string, string> */
    private function organizationNames(int $userId): array
    {
        $names = [];
        foreach ($this->organizations->forUser($userId) as $organization) {
            $names[$organization['id']] = $organization['name'];
        }

        return $names;
    }

    /**
     * @param  array<string, string>  $organizationNames
     * @return array{licenses: array<int, array<string, mixed>>, total: int}
     */
    private function licenseRecords(int $userId, array $organizationNames): array
    {
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
                'state' => self::state((array) $license, $now),
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

        return ['licenses' => $safeLicenses, 'total' => $total];
    }

    /** @param array<string, mixed> $license */
    public static function state(array $license, Carbon $now): string
    {
        if (($license['revoked_at'] ?? null) !== null) {
            return 'REVOKED';
        }
        if (($license['status'] ?? null) !== 'active') {
            return 'RESTRICTED';
        }
        $startsAt = (string) ($license['starts_at'] ?? '');
        $expiresAt = (string) ($license['expires_at'] ?? '');
        if ($startsAt === '' || $expiresAt === '') {
            return 'RESTRICTED';
        }
        if ($now->lt(Carbon::parse($startsAt))) {
            return 'NOT_STARTED';
        }
        if ($now->lt(Carbon::parse($expiresAt))) {
            return $now->copy()->addDays(7)->gte(Carbon::parse($expiresAt))
                ? 'RENEWAL_DUE' : 'ACTIVE';
        }
        $graceUntil = $license['grace_until'] ?? null;
        if (is_string($graceUntil) && $now->lt(Carbon::parse($graceUntil))) {
            return 'GRACE';
        }

        return 'RESTRICTED';
    }
}
