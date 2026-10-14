<?php

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;

final class KslpKeyRegistry
{
    public const PURPOSES = ['license', 'release', 'evidence'];

    public const PUBLISHABLE_STATUSES = ['active', 'retiring'];

    /**
     * Register canonical base64url-encoded Ed25519 public key material.
     *
     * Binary Ed25519 keys cannot be stored in PostgreSQL TEXT (which rejects
     * NUL bytes). Both discovery and persisted key material are base64url;
     * publicKey() decodes to exactly 32 raw bytes for sodium verification.
     */
    public function publish(
        string $kid,
        string $purpose,
        string $publicKey,
        string $status = 'active',
    ): void {
        if (! in_array($purpose, self::PURPOSES, true)) {
            throw new DomainException('KSLP_INVALID_KEY_PURPOSE');
        }
        if (! in_array($status, self::PUBLISHABLE_STATUSES, true)) {
            throw new DomainException('KSLP_INVALID_KEY_STATUS');
        }
        if (! preg_match('/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/D', $kid)) {
            throw new DomainException('KSLP_INVALID_PUBLIC_KEY');
        }
        self::decodeEd25519PublicKey($publicKey);

        DB::transaction(function () use ($kid, $purpose, $publicKey, $status): void {
            $existing = DB::table('kslp_signing_keys')
                ->where('kid', $kid)
                ->lockForUpdate()
                ->first();

            if ($existing) {
                if (
                    ! hash_equals((string) $existing->purpose, $purpose)
                    || ! hash_equals((string) $existing->public_key, $publicKey)
                ) {
                    throw new DomainException('KSLP_KEY_IDENTITY_CONFLICT');
                }
                if ($existing->revoked_at !== null || $existing->status === 'revoked') {
                    throw new DomainException('KSLP_KEY_REVOKED');
                }

                DB::table('kslp_signing_keys')
                    ->where('kid', $kid)
                    ->update(['status' => $status, 'updated_at' => now()]);

                return;
            }

            $now = now();
            DB::table('kslp_signing_keys')->insert([
                'kid' => $kid,
                'purpose' => $purpose,
                'public_key' => $publicKey,
                'status' => $status,
                'not_before' => $now,
                'not_after' => null,
                'revoked_at' => null,
                'created_at' => $now,
                'updated_at' => $now,
            ]);
        }, 3);
    }

    public function revoke(string $kid): void
    {
        if (
            DB::table('kslp_signing_keys')
                ->where('kid', $kid)
                ->whereNull('revoked_at')
                ->update([
                    'status' => 'revoked',
                    'revoked_at' => now(),
                    'updated_at' => now(),
                ]) !== 1
        ) {
            throw new DomainException('KSLP_UNKNOWN_KID');
        }
    }

    /**
     * Public keysets are discoverable only during the recorded validity window.
     * Expired/future keys must not remain published for new verifications.
     *
     * @return array<array-key, mixed>
     */
    public function discovery(string $purpose): array
    {
        if (! in_array($purpose, self::PURPOSES, true)) {
            throw new DomainException('KSLP_INVALID_KEY_PURPOSE');
        }

        return DB::table('kslp_signing_keys')
            ->where('purpose', $purpose)
            ->whereIn('status', self::PUBLISHABLE_STATUSES)
            ->whereNull('revoked_at')
            ->where('not_before', '<=', now())
            ->where(fn ($query) => $query->whereNull('not_after')->orWhere('not_after', '>', now()))
            ->orderBy('not_before')
            ->get(['kid', 'purpose', 'public_key', 'status', 'not_before', 'not_after'])
            ->map(fn ($key): array => (array) $key)
            ->all();
    }

    /** Get the raw 32-byte key expected by sodium_crypto_sign_verify_detached. */
    public function publicKey(string $kid, string $purpose): string
    {
        if (! in_array($purpose, self::PURPOSES, true)) {
            throw new DomainException('KSLP_INVALID_KEY_PURPOSE');
        }

        $key = DB::table('kslp_signing_keys')
            ->where('kid', $kid)
            ->where('purpose', $purpose)
            ->whereIn('status', self::PUBLISHABLE_STATUSES)
            ->whereNull('revoked_at')
            ->where('not_before', '<=', now())
            ->where(fn ($query) => $query->whereNull('not_after')->orWhere('not_after', '>', now()))
            ->first();

        if (! $key) {
            throw new DomainException('KSLP_UNKNOWN_KID');
        }

        return self::decodeEd25519PublicKey((string) $key->public_key);
    }

    private static function decodeEd25519PublicKey(string $encoded): string
    {
        if (! preg_match('/^[A-Za-z0-9_-]{43}$/D', $encoded)) {
            throw new DomainException('KSLP_INVALID_PUBLIC_KEY');
        }

        $raw = base64_decode(strtr($encoded, '-_', '+/').'=', true);
        if (
            $raw === false
            || strlen($raw) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES
            || rtrim(strtr(base64_encode($raw), '+/', '-_'), '=') !== $encoded
        ) {
            throw new DomainException('KSLP_INVALID_PUBLIC_KEY');
        }

        return $raw;
    }
}
