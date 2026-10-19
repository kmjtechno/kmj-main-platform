<?php

declare(strict_types=1);

namespace App\Services\Payments;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Contracts\Encryption\DecryptException;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use InvalidArgumentException;

final class OwnerPaymentGatewaySettings
{
    /** @var list<string> */
    private const PROVIDERS = ['cashfree', 'razorpay'];

    /** @return list<array<string, bool|string|null>> */
    public function snapshot(): array
    {
        // A code-first staging rollout must not make the owner console error
        // before the migration has been applied.
        $storageReady = Schema::hasTable('payment_gateway_settings');
        $rows = $storageReady
            ? DB::table('payment_gateway_settings')->get()->keyBy('provider')
            : collect();

        return array_map(static function (string $provider) use ($rows, $storageReady): array {
            $row = $rows->get($provider);
            // Ciphertext existing in the DB does not prove it can be
            // decrypted or used by the sandbox provider.
            $storedClientIdValid = self::usableStoredCredential($row?->encrypted_client_id, $provider, true);
            $storedClientSecretValid = self::usableStoredCredential($row?->encrypted_client_secret, $provider, false);

            return [
                'provider' => $provider,
                'storage_ready' => $storageReady,
                'name' => $provider === 'cashfree' ? 'Cashfree Payments' : 'Razorpay',
                'environment' => 'sandbox',
                'merchant_status' => $row === null ? 'not_verified' : (string) $row->merchant_status,
                'international_requested' => $row !== null && (bool) $row->international_requested,
                'client_id_stored' => $storedClientIdValid,
                'client_secret_stored' => $storedClientSecretValid,
                'webhook_secret_stored' => $row?->encrypted_webhook_secret !== null,
                'last_updated' => $row?->updated_at,
                'live_charging_enabled' => false,
                'sandbox_transaction_verified' => false,
                'note' => 'Credentials saved securely, but provider connection and sandbox checkout are not yet verified.',
            ];
        }, self::PROVIDERS);
    }

    /**
     * Save encrypted test credentials and non-authoritative merchant setup notes.
     * Secrets never return to the browser, audit, log, or session.
     *
     * @param  array<string, mixed>  $input
     */
    public function save(User $actor, string $provider, array $input): void
    {
        $this->ensureProvider($provider);

        if (($input['environment'] ?? 'sandbox') !== 'sandbox') {
            throw new InvalidArgumentException('Only sandbox configuration is supported.');
        }

        $changedSecrets = [];
        $encrypted = [];
        foreach ([
            'client_id' => 'encrypted_client_id',
            'client_secret' => 'encrypted_client_secret',
            'webhook_secret' => 'encrypted_webhook_secret',
        ] as $inputName => $column) {
            $plain = $input[$inputName] ?? null;
            if (is_string($plain) && $plain !== '') {
                if ($provider === 'razorpay' && $inputName === 'client_id'
                    && ! self::validRazorpaySandboxKey($plain)) {
                    throw new InvalidArgumentException('Razorpay test keys only.');
                }

                $encrypted[$column] = Crypt::encryptString($plain);
                $changedSecrets[] = $inputName;
            }
        }

        DB::transaction(static function () use ($actor, $provider, $input, $encrypted, $changedSecrets): void {
            $existing = DB::table('payment_gateway_settings')->where('provider', $provider)->first();

            $values = [
                'environment' => 'sandbox',
                'merchant_status' => $input['merchant_status'] ?? 'not_verified',
                'international_requested' => (bool) ($input['international_requested'] ?? false),
                'updated_by' => $actor->getKey(),
                'updated_at' => now(),
                ...$encrypted,
            ];

            if ($existing === null) {
                DB::table('payment_gateway_settings')->insert([
                    'provider' => $provider,
                    'created_at' => now(),
                    ...$values,
                ]);
            } else {
                DB::table('payment_gateway_settings')->where('provider', $provider)->update($values);
            }

            OperatorActionAudit::query()->create([
                'actor_user_id' => $actor->getKey(),
                'action' => 'payment_gateway.sandbox_settings_saved',
                'outcome' => 'saved_unverified',
                'metadata' => [
                    'provider' => $provider,
                    'changed_secret_fields' => $changedSecrets,
                    'live_charging_enabled' => false,
                ],
            ]);
        });
    }

    public function revoke(User $actor, string $provider): void
    {
        $this->ensureProvider($provider);

        DB::transaction(static function () use ($actor, $provider): void {
            DB::table('payment_gateway_settings')->where('provider', $provider)->update([
                'encrypted_client_id' => null,
                'encrypted_client_secret' => null,
                'encrypted_webhook_secret' => null,
                'updated_by' => $actor->getKey(),
                'updated_at' => now(),
            ]);

            OperatorActionAudit::query()->create([
                'actor_user_id' => $actor->getKey(),
                'action' => 'payment_gateway.sandbox_credentials_revoked',
                'outcome' => 'revoked',
                'metadata' => [
                    'provider' => $provider,
                    'live_charging_enabled' => false,
                ],
            ]);
        });
    }

    /**
     * Internal-only test credentials. Never expose through Inertia, JSON or logs.
     *
     * @return array{client_id: string, client_secret: string}
     */
    public function sandboxCredentials(string $provider): array
    {
        $this->ensureProvider($provider);

        if (! Schema::hasTable('payment_gateway_settings')) {
            throw new InvalidArgumentException('SANDBOX_CREDENTIALS_NOT_READY');
        }

        $record = DB::table('payment_gateway_settings')->where('provider', $provider)->first();
        if ($record === null || $record->environment !== 'sandbox'
            || ! is_string($record->encrypted_client_id)
            || ! is_string($record->encrypted_client_secret)) {
            throw new InvalidArgumentException('SANDBOX_CREDENTIALS_NOT_READY');
        }

        try {
            $id = Crypt::decryptString($record->encrypted_client_id);
            $secret = Crypt::decryptString($record->encrypted_client_secret);
        } catch (DecryptException) {
            // Never surface invalid ciphertext or decrypt internals to the
            // owner session. A corrupt vault is unready, not a provider error.
            throw new InvalidArgumentException('SANDBOX_CREDENTIALS_NOT_READY');
        }

        if (! self::usableCredential($id, $provider, true)
            || ! self::usableCredential($secret, $provider, false)) {
            throw new InvalidArgumentException('SANDBOX_CREDENTIALS_NOT_READY');
        }

        return ['client_id' => $id, 'client_secret' => $secret];
    }

    private static function usableStoredCredential(mixed $encrypted, string $provider, bool $isClientId): bool
    {
        if (! is_string($encrypted) || $encrypted === '') {
            return false;
        }

        try {
            return self::usableCredential(Crypt::decryptString($encrypted), $provider, $isClientId);
        } catch (DecryptException) {
            return false;
        }
    }

    private static function usableCredential(string $plain, string $provider, bool $isClientId): bool
    {
        if ($plain === '' || strlen($plain) > ($isClientId ? 255 : 1024)
            || preg_match('/[\\x00-\\x1F\\x7F]/', $plain)) {
            return false;
        }

        return ! $isClientId || $provider !== 'razorpay' || self::validRazorpaySandboxKey($plain);
    }

    private static function validRazorpaySandboxKey(mixed $key): bool
    {
        return is_string($key) && (bool) preg_match('/\\Arzp_test_[A-Za-z0-9]+\\z/D', $key);
    }

    private function ensureProvider(string $provider): void
    {
        if (! in_array($provider, self::PROVIDERS, true)) {
            throw new InvalidArgumentException('Unsupported payment provider.');
        }
    }
}
