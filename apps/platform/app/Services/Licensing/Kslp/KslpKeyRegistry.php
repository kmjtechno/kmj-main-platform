<?php

namespace App\Services\Licensing\Kslp;

use DomainException;
use Illuminate\Support\Facades\DB;

final class KslpKeyRegistry
{
    public const PURPOSES = ['license', 'release', 'evidence'];

    public const PUBLISHABLE_STATUSES = ['active', 'retiring'];

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
        if (trim($kid) === '' || trim($publicKey) === '') {
            throw new DomainException('KSLP_INVALID_PUBLIC_KEY');
        }

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

    public function discovery(string $purpose): array
    {
        if (! in_array($purpose, self::PURPOSES, true)) {
            throw new DomainException('KSLP_INVALID_KEY_PURPOSE');
        }

        return DB::table('kslp_signing_keys')
            ->where('purpose', $purpose)
            ->whereIn('status', self::PUBLISHABLE_STATUSES)
            ->whereNull('revoked_at')
            ->orderBy('not_before')
            ->get(['kid', 'purpose', 'public_key', 'status', 'not_before', 'not_after'])
            ->map(fn ($key): array => (array) $key)
            ->all();
    }

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
            ->first();

        if (! $key) {
            throw new DomainException('KSLP_UNKNOWN_KID');
        }

        return (string) $key->public_key;
    }
}
