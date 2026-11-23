<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Commerce\KmjProductCatalog;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;

final class OmniDeskActivationQueryService
{
    /**
     * @return array{
     *   activation_id:string,
     *   state:string,
     *   reason_codes:list<string>,
     *   current_sequence:int,
     *   server_time:int
     * }
     */
    public function status(string $activationId, OmniDeskApiPrincipal $principal): array
    {
        [$binding, $activation, $license] = $this->recordsForPrincipal($activationId, $principal);
        $reasonCodes = [];

        if ($activation['deactivated_at'] !== null) {
            $reasonCodes[] = 'ACTIVATION_REVOKED';
        }
        if ($license['revoked_at'] !== null || (string) $license['status'] === 'revoked') {
            $reasonCodes[] = 'LICENSE_REVOKED';
        } elseif ((string) $license['status'] !== 'active') {
            // The shared CloudOS-oriented KSLP state helper considers dates
            // but does not independently reject a paused OmniDesk license.
            $reasonCodes[] = 'LICENSE_INACTIVE';
        }
        if ($license['starts_at'] === null || now()->lt($license['starts_at'])) {
            $reasonCodes[] = 'LICENSE_NOT_YET_ACTIVE';
        }
        if ((int) $binding['current_sequence'] < 1
            || ! is_string($binding['current_jti'])
            || trim($binding['current_jti']) === '') {
            // bind() creates a row at sequence 0 BEFORE an actual signed lease
            // exists. Never present this unsent activation as licensed/ACTIVE.
            $reasonCodes[] = 'LEASE_NOT_ISSUED';
        }

        // Revocation/plan changes after activation must not turn a stale
        // binding into an apparently ACTIVE OmniDesk license.
        $productId = Product::query()
            ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
            ->value('id');
        $entitlementRow = $productId === null ? null : DB::table('entitlements')
            ->where('id', $binding['entitlement_id'])
            ->where('organization_id', $principal->organizationId)
            ->where('product_id', $productId)
            ->where('capability', OmniDeskLicenseContract::CAPABILITY)
            ->first(['status', 'starts_at', 'ends_at']);

        if ($entitlementRow === null) {
            $reasonCodes[] = 'ENTITLEMENT_INACTIVE';
        } else {
            /** @var array{status:string,starts_at:mixed,ends_at:mixed} $entitlement */
            $entitlement = (array) $entitlementRow;
            $now = now();
            if ((string) $entitlement['status'] !== 'active') {
                $reasonCodes[] = 'ENTITLEMENT_REVOKED';
            } elseif ($entitlement['starts_at'] === null || $now->lt($entitlement['starts_at'])) {
                $reasonCodes[] = 'ENTITLEMENT_NOT_YET_ACTIVE';
            } elseif ($entitlement['ends_at'] !== null && $now->gte($entitlement['ends_at'])) {
                $reasonCodes[] = 'ENTITLEMENT_EXPIRED';
            }
        }

        $explicitlyRevoked = array_intersect(
            $reasonCodes,
            ['ACTIVATION_REVOKED', 'LICENSE_REVOKED', 'ENTITLEMENT_REVOKED'],
        ) !== [];

        if ($explicitlyRevoked) {
            $state = 'REVOKED';
        } elseif ($reasonCodes !== []) {
            $state = 'RESTRICTED';
        } else {
            $state = app(KslpLicenseControlPlane::class)->state((string) $activation['license_id']);
        }

        return [
            'activation_id' => $activationId,
            'state' => $state,
            'reason_codes' => $reasonCodes,
            'current_sequence' => (int) $binding['current_sequence'],
            'server_time' => time(),
        ];
    }

    /**
     * @return array{
     *   product_id:string,
     *   product_slug:string,
     *   entitlements:list<array{
     *     entitlement_id:string,
     *     status:string,
     *     starts_at:string,
     *     ends_at:?string
     *   }>,
     *   server_time:int
     * }
     */
    public function currentEntitlements(OmniDeskApiPrincipal $principal): array
    {
        $product = Product::query()
            ->where('slug', KmjProductCatalog::OMNIDESK_SLUG)
            ->first(['id', 'slug']);
        if (! $product instanceof Product) {
            throw new DomainException('OMNIDESK_PRODUCT_NOT_FOUND');
        }

        $entitlements = array_values(DB::table('entitlements')
            ->where('organization_id', $principal->organizationId)
            ->where('product_id', $product->getKey())
            ->where('capability', OmniDeskLicenseContract::CAPABILITY)
            ->orderByDesc('created_at')
            ->get(['id', 'status', 'starts_at', 'ends_at'])
            ->map(static function (object $row): array {
                /** @var array{id:mixed,status:mixed,starts_at:mixed,ends_at:mixed} $data */
                $data = (array) $row;

                return [
                    'entitlement_id' => (string) $data['id'],
                    'status' => (string) $data['status'],
                    'starts_at' => (string) $data['starts_at'],
                    'ends_at' => $data['ends_at'] === null ? null : (string) $data['ends_at'],
                ];
            })
            ->all());

        return [
            'product_id' => OmniDeskLicenseContract::PRODUCT_ID,
            'product_slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'entitlements' => $entitlements,
            'server_time' => time(),
        ];
    }

    /**
     * @return array{
     *   activation_id:string,
     *   state:string,
     *   reason_codes:list<string>,
     *   current_sequence:int,
     *   server_time:int
     * }
     */
    public function deactivate(
        string $activationId,
        OmniDeskApiPrincipal $principal,
        string $reason,
    ): array {
        if (! $principal->canManage) {
            throw new DomainException('OMNIDESK_FORBIDDEN');
        }
        $reason = trim($reason);
        if (mb_strlen($reason) < 3 || mb_strlen($reason) > 500) {
            throw new DomainException('OMNIDESK_REASON_REQUIRED');
        }

        DB::transaction(function () use ($activationId, $principal, $reason): void {
            [$binding, $activation] = $this->recordsForPrincipal(
                $activationId,
                $principal,
                true,
            );

            if ($activation['deactivated_at'] !== null) {
                return;
            }

            $now = now();
            DB::table('kslp_activations')
                ->where('id', $activationId)
                ->whereNull('deactivated_at')
                ->update([
                    'deactivated_at' => $now,
                    'updated_at' => $now,
                ]);

            DB::table('kslp_license_events')->insert([
                'license_id' => (string) $activation['license_id'],
                'actor_id' => $principal->actorId,
                'action' => 'omnidesk_activation_deactivated',
                'reason' => $reason,
                'correlation_id' => (string) Str::uuid(),
                'metadata' => json_encode([
                    'activation_id' => $activationId,
                    'entitlement_id' => (string) $binding['entitlement_id'],
                ], JSON_THROW_ON_ERROR),
                'created_at' => $now,
            ]);
        }, 3);

        return $this->status($activationId, $principal);
    }

    /**
     * @return array{
     *   0:array{
     *     activation_id:string,
     *     entitlement_id:string,
     *     organization_id:string,
     *     current_sequence:int|string,
     *     current_jti:?string
     *   },
     *   1:array{
     *     id:string,
     *     license_id:string,
     *     deactivated_at:mixed
     *   },
     *   2:array{
     *     id:string,
     *     status:string,
     *     revoked_at:mixed,
     *     starts_at:mixed
     *   }
     * }
     */
    private function recordsForPrincipal(
        string $activationId,
        OmniDeskApiPrincipal $principal,
        bool $lock = false,
    ): array {
        if ($lock) {
            return $this->lockedRecordsForPrincipal($activationId, $principal);
        }

        $bindingQuery = DB::table('omnidesk_activation_bindings')
            ->where('activation_id', $activationId);
        $bindingRow = $bindingQuery->first();

        if ($bindingRow === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }
        /** @var array{
         *   activation_id:string,
         *   entitlement_id:string,
         *   organization_id:string,
         *   current_sequence:int|string,
         *   current_jti:?string
         * } $binding
         */
        $binding = (array) $bindingRow;
        if (! hash_equals((string) $binding['organization_id'], $principal->organizationId)) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }

        $activationQuery = DB::table('kslp_activations')
            ->where('id', $activationId);
        $activationRow = $activationQuery->first();
        if ($activationRow === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }
        /** @var array{id:string,license_id:string,deactivated_at:mixed} $activation */
        $activation = (array) $activationRow;

        $licenseQuery = DB::table('kslp_licenses')
            ->where('id', $activation['license_id'])
            ->where('customer_id', $principal->organizationId)
            ->where('product', OmniDeskLicenseContract::PRODUCT_ID);
        $licenseRow = $licenseQuery->first();
        if ($licenseRow === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }
        /** @var array{id:string,status:string,revoked_at:mixed,starts_at:mixed} $license */
        $license = (array) $licenseRow;

        return [$binding, $activation, $license];
    }

    /**
     * Acquire locks in the same order as OmniDeskActivationBindingStore::advanceLease:
     * license -> activation -> binding. Non-locking lookups are identifiers
     * only and MUST be rechecked after the authoritative locks are held.
     *
     * @return array{array{activation_id:string,entitlement_id:string,organization_id:string,current_sequence:int|string,current_jti:?string},array{id:string,license_id:string,deactivated_at:mixed},array{id:string,status:string,revoked_at:mixed,starts_at:mixed}}
     */
    private function lockedRecordsForPrincipal(
        string $activationId,
        OmniDeskApiPrincipal $principal,
    ): array {
        $previewBinding = DB::table('omnidesk_activation_bindings')
            ->where('activation_id', $activationId)
            ->first(['organization_id']);
        if ($previewBinding === null
            || ! hash_equals((string) $previewBinding->organization_id, $principal->organizationId)) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }

        $previewActivation = DB::table('kslp_activations')
            ->where('id', $activationId)
            ->first(['license_id']);
        if ($previewActivation === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }

        $licenseRow = DB::table('kslp_licenses')
            ->where('id', $previewActivation->license_id)
            ->where('customer_id', $principal->organizationId)
            ->where('product', OmniDeskLicenseContract::PRODUCT_ID)
            ->lockForUpdate()
            ->first();
        if ($licenseRow === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }

        $activationRow = DB::table('kslp_activations')
            ->where('id', $activationId)
            ->where('license_id', $licenseRow->id)
            ->lockForUpdate()
            ->first();
        if ($activationRow === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }

        $bindingRow = DB::table('omnidesk_activation_bindings')
            ->where('activation_id', $activationId)
            ->where('organization_id', $principal->organizationId)
            ->lockForUpdate()
            ->first();
        if ($bindingRow === null) {
            throw new DomainException('OMNIDESK_ACTIVATION_NOT_FOUND');
        }

        /** @var array{activation_id:string,entitlement_id:string,organization_id:string,current_sequence:int|string,current_jti:?string} $binding */
        $binding = (array) $bindingRow;
        /** @var array{id:string,license_id:string,deactivated_at:mixed} $activation */
        $activation = (array) $activationRow;
        /** @var array{id:string,status:string,revoked_at:mixed,starts_at:mixed} $license */
        $license = (array) $licenseRow;

        return [$binding, $activation, $license];
    }
}
