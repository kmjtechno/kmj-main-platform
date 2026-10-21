<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Commerce\KmjProductCatalog;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

final class OmniDeskActivationPairingService
{
    public function __construct(
        private readonly OrganizationDirectory $organizations,
        private readonly OrganizationCapabilityContext $capabilities,
        private readonly OmniDeskActivationGrantStore $grants,
    ) {}

    /**
     * @param array{
     *   device_public_key:string,
     *   device_public_key_fingerprint:string,
     *   installation_id:string,
     *   platform:string,
     *   arch:string,
     *   client_version:string,
     *   code_challenge:string
     * } $input
     * @return array{
     *   device_code:string,
     *   user_code:string,
     *   verification_uri:string,
     *   verification_uri_complete:string,
     *   expires_in:int,
     *   interval:int
     * }
     */
    public function create(array $input, int $now): array
    {
        $this->validateDeviceIdentity(
            $input['device_public_key'],
            $input['device_public_key_fingerprint'],
            $input['installation_id'],
        );
        if (preg_match('/\A[A-Za-z0-9_-]{43,128}\z/D', $input['code_challenge']) !== 1) {
            throw new DomainException('OMNIDESK_PAIRING_INVALID');
        }

        $deviceCode = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
        $userCode = $this->humanCode();
        $id = (string) Str::uuid();

        DB::table('omnidesk_activation_pairings')->insert([
            'id' => $id,
            'device_code_hash' => hash('sha256', $deviceCode),
            'user_code_hash' => hash('sha256', $userCode),
            'device_public_key' => $input['device_public_key'],
            'device_public_key_fingerprint' => $input['device_public_key_fingerprint'],
            'installation_id' => $input['installation_id'],
            'platform' => $input['platform'],
            'arch' => $input['arch'],
            'client_version' => $input['client_version'],
            'code_challenge' => $input['code_challenge'],
            'status' => 'pending',
            'expires_at' => gmdate('Y-m-d H:i:s', $now + 300),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $displayCode = substr($userCode, 0, 4).'-'.substr($userCode, 4);
        $base = rtrim((string) config('app.url'), '/');

        return [
            'device_code' => $deviceCode,
            'user_code' => $displayCode,
            'verification_uri' => $base.'/omnidesk/pair',
            'verification_uri_complete' => $base.'/omnidesk/pair?code='.rawurlencode($displayCode),
            'expires_in' => 300,
            'interval' => 5,
        ];
    }

    /**
     * @return array{
     *   code:string,
     *   device_public_key_fingerprint:string,
     *   installation_id:string,
     *   platform:string,
     *   arch:string,
     *   client_version:string,
     *   expires_at:string,
     *   organizations:list<array{
     *     id:string,
     *     name:string,
     *     entitlements:list<array{id:string}>
     *   }>
     * }|null
     */
    public function preview(string $displayCode, int $userId, int $now): ?array
    {
        $code = $this->normalizeUserCode($displayCode);
        if ($code === null) {
            return null;
        }

        $row = DB::table('omnidesk_activation_pairings')
            ->where('user_code_hash', hash('sha256', $code))
            ->where('status', 'pending')
            ->where('expires_at', '>', gmdate('Y-m-d H:i:s', $now))
            ->first();
        if ($row === null) {
            return null;
        }

        /** @var array{
         *   device_public_key_fingerprint:string,
         *   installation_id:string,
         *   platform:string,
         *   arch:string,
         *   client_version:string,
         *   expires_at:string
         * } $pairing
         */
        $pairing = (array) $row;

        $product = Product::query()
            ->where('slug', KmjProductCatalog::OMNIDESK_SLUG)
            ->where('status', 'active')
            ->first(['id']);
        if (! $product instanceof Product) {
            return null;
        }

        $eligible = [];
        foreach ($this->organizations->forUser($userId) as $organization) {
            if (! $this->capabilities->allows($userId, $organization['id'], 'license.manage')) {
                continue;
            }

            $entitlements = Entitlement::query()
                ->where('organization_id', $organization['id'])
                ->where('product_id', $product->getKey())
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->where('starts_at', '<=', now())
                ->where(static function ($query): void {
                    $query->whereNull('ends_at')->orWhere('ends_at', '>', now());
                })
                ->orderBy('created_at')
                ->get(['id'])
                ->map(static fn (Entitlement $entitlement): array => [
                    'id' => (string) $entitlement->getKey(),
                ])
                ->values()
                ->all();

            if ($entitlements !== []) {
                $eligible[] = [
                    'id' => $organization['id'],
                    'name' => $organization['name'],
                    'entitlements' => $entitlements,
                ];
            }
        }

        return [
            'code' => $displayCode,
            'device_public_key_fingerprint' => $pairing['device_public_key_fingerprint'],
            'installation_id' => $pairing['installation_id'],
            'platform' => $pairing['platform'],
            'arch' => $pairing['arch'],
            'client_version' => $pairing['client_version'],
            'expires_at' => $pairing['expires_at'],
            'organizations' => $eligible,
        ];
    }

    public function approve(
        string $displayCode,
        int $userId,
        string $organizationId,
        string $entitlementId,
        int $now,
    ): void {
        if (! $this->capabilities->allows($userId, $organizationId, 'license.manage')) {
            throw new DomainException('OMNIDESK_PAIRING_DENIED');
        }

        $code = $this->normalizeUserCode($displayCode);
        if ($code === null) {
            throw new DomainException('OMNIDESK_PAIRING_INVALID');
        }

        DB::transaction(function () use (
            $code,
            $organizationId,
            $entitlementId,
            $now,
        ): void {
            $row = DB::table('omnidesk_activation_pairings')
                ->where('user_code_hash', hash('sha256', $code))
                ->lockForUpdate()
                ->first();
            if ($row === null) {
                throw new DomainException('OMNIDESK_PAIRING_EXPIRED');
            }
            /** @var array{id:string,status:string,expires_at:string} $pairing */
            $pairing = (array) $row;
            if ($pairing['status'] !== 'pending'
                || strtotime($pairing['expires_at']) <= $now) {
                throw new DomainException('OMNIDESK_PAIRING_EXPIRED');
            }

            $product = Product::query()
                ->where('slug', KmjProductCatalog::OMNIDESK_SLUG)
                ->where('status', 'active')
                ->first(['id']);
            if (! $product instanceof Product) {
                throw new DomainException('OMNIDESK_PAIRING_DENIED');
            }

            $entitlement = Entitlement::query()
                ->whereKey($entitlementId)
                ->where('organization_id', $organizationId)
                ->where('product_id', $product->getKey())
                ->where('capability', OmniDeskLicenseContract::CAPABILITY)
                ->where('status', 'active')
                ->where('starts_at', '<=', now())
                ->where(static function ($query): void {
                    $query->whereNull('ends_at')->orWhere('ends_at', '>', now());
                })
                ->lockForUpdate()
                ->first();
            if (! $entitlement instanceof Entitlement) {
                throw new DomainException('OMNIDESK_PAIRING_DENIED');
            }

            DB::table('omnidesk_activation_pairings')
                ->where('id', $pairing['id'])
                ->update([
                    'status' => 'approved',
                    'organization_id' => $organizationId,
                    'entitlement_id' => $entitlementId,
                    'approved_at' => now(),
                    'updated_at' => now(),
                ]);
        }, 3);
    }

    /**
     * @return array{
     *   activation_grant:string,
     *   expires_in:int,
     *   organization_id:string,
     *   entitlement_id:string
     * }
     */
    public function redeem(
        string $deviceCode,
        string $verifier,
        string $deviceFingerprint,
        string $installationId,
        int $now,
    ): array {
        return DB::transaction(function () use (
            $deviceCode,
            $verifier,
            $deviceFingerprint,
            $installationId,
            $now,
        ): array {
            $row = DB::table('omnidesk_activation_pairings')
                ->where('device_code_hash', hash('sha256', $deviceCode))
                ->lockForUpdate()
                ->first();
            if ($row === null) {
                throw new DomainException('OMNIDESK_PAIRING_EXPIRED');
            }

            /** @var array{
             *   id:string,
             *   status:string,
             *   expires_at:string,
             *   consumed_at:mixed,
             *   organization_id:string|null,
             *   entitlement_id:string|null,
             *   device_public_key:string,
             *   device_public_key_fingerprint:string,
             *   installation_id:string,
             *   code_challenge:string
             * } $pairing
             */
            $pairing = (array) $row;

            if (strtotime($pairing['expires_at']) <= $now) {
                throw new DomainException('OMNIDESK_PAIRING_EXPIRED');
            }
            if ($pairing['status'] === 'pending') {
                throw new DomainException('OMNIDESK_PAIRING_PENDING');
            }
            if ($pairing['status'] !== 'approved'
                || $pairing['consumed_at'] !== null
                || ! is_string($pairing['organization_id'])
                || ! is_string($pairing['entitlement_id'])) {
                throw new DomainException('OMNIDESK_PAIRING_CONSUMED');
            }
            if (! hash_equals($pairing['device_public_key_fingerprint'], $deviceFingerprint)
                || ! hash_equals($pairing['installation_id'], $installationId)) {
                throw new DomainException('OMNIDESK_PAIRING_INVALID');
            }

            $challenge = rtrim(
                strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'),
                '=',
            );
            if (! hash_equals($pairing['code_challenge'], $challenge)) {
                throw new DomainException('OMNIDESK_PAIRING_INVALID');
            }

            $grant = $this->grants->issue([
                'id' => $pairing['id'],
                'organization_id' => $pairing['organization_id'],
                'entitlement_id' => $pairing['entitlement_id'],
                'device_public_key' => $pairing['device_public_key'],
                'device_public_key_fingerprint' => $pairing['device_public_key_fingerprint'],
                'installation_id' => $pairing['installation_id'],
            ], $now);

            DB::table('omnidesk_activation_pairings')
                ->where('id', $pairing['id'])
                ->update([
                    'status' => 'consumed',
                    'consumed_at' => now(),
                    'updated_at' => now(),
                ]);

            return [
                'activation_grant' => $grant['grant'],
                'expires_in' => $grant['expires_in'],
                'organization_id' => $pairing['organization_id'],
                'entitlement_id' => $pairing['entitlement_id'],
            ];
        }, 3);
    }

    private function validateDeviceIdentity(
        string $devicePublicKey,
        string $deviceFingerprint,
        string $installationId,
    ): void {
        if (preg_match('/\A[A-Za-z0-9_-]{43}\z/D', $devicePublicKey) !== 1
            || strlen($installationId) < 8
            || strlen($installationId) > 256) {
            throw new DomainException('OMNIDESK_PAIRING_INVALID');
        }

        $padding = (4 - strlen($devicePublicKey) % 4) % 4;
        $raw = base64_decode(
            strtr($devicePublicKey, '-_', '+/').str_repeat('=', $padding),
            true,
        );
        if ($raw === false || strlen($raw) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
            throw new DomainException('OMNIDESK_PAIRING_INVALID');
        }

        $expected = 'sha256:'.hash('sha256', $raw);
        if (! hash_equals($expected, $deviceFingerprint)) {
            throw new DomainException('OMNIDESK_PAIRING_INVALID');
        }
    }

    private function humanCode(): string
    {
        $alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        $code = '';
        for ($index = 0; $index < 8; $index++) {
            $code .= $alphabet[random_int(0, strlen($alphabet) - 1)];
        }

        return $code;
    }

    private function normalizeUserCode(string $displayCode): ?string
    {
        $code = strtoupper(str_replace('-', '', trim($displayCode)));

        return preg_match('/\A[A-Z2-9]{8}\z/D', $code) === 1 ? $code : null;
    }
}
