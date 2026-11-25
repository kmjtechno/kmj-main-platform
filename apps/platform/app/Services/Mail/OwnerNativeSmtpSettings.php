<?php

declare(strict_types=1);

namespace App\Services\Mail;

use App\Mail\NativeExternalMailMessage;
use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Contracts\Encryption\DecryptException;
use Illuminate\Mail\SentMessage;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Schema;
use Illuminate\Validation\ValidationException;
use Throwable;

/**
 * Admin selection of server-pinned SMTP profiles, not an arbitrary relay.
 * Remote credentials are encrypted at rest or supplied by the server;
 * they never appear in browser props.
 */
final class OwnerNativeSmtpSettings
{
    public function __construct(
        private readonly PlatformOwnerAccess $owner,
        private readonly RegistrationMailReadiness $readiness,
    ) {}

    public function installed(): bool
    {
        return Schema::hasTable('kmj_native_smtp_settings');
    }

    public function activeProfile(): string
    {
        if (! $this->installed()) {
            return 'loopback';
        }

        $profile = DB::table('kmj_native_smtp_settings')->where('id', 1)->value('active_profile');

        return $profile === null ? 'loopback' : (string) $profile;
    }

    public function ready(string $profile): bool
    {
        if (config('services.kmj_native_external_mail.enabled', false) !== true
            || config('services.kmj_native_external_mail.transport') !== 'loopback_smtp'
            || ! $this->readiness->canAttemptDelivery()) {
            return false;
        }

        if ($profile === 'loopback') {
            return config('mail.mailers.kmj_native_loopback.transport') === 'smtp'
                && config('mail.mailers.kmj_native_loopback.host') === '127.0.0.1'
                && config('mail.mailers.kmj_native_loopback.port') === 25
                && config('mail.mailers.kmj_native_loopback.scheme') === null
                && config('mail.mailers.kmj_native_loopback.auto_tls') === false
                && config('mail.mailers.kmj_native_loopback.username') === null
                && config('mail.mailers.kmj_native_loopback.password') === null
                && config('mail.mailers.kmj_native_loopback.timeout') === 8
                && config('mail.mailers.kmj_native_loopback.local_domain') === 'kmjtechno.com'
                && config('mail.mailers.kmj_native_loopback.url') === null;
        }

        if ($profile !== 'brevo') {
            return false;
        }

        $credentials = $this->brevoCredentials();

        return config('mail.mailers.kmj_brevo.transport') === 'smtp'
            && config('mail.mailers.kmj_brevo.scheme') === 'smtps'
            && config('mail.mailers.kmj_brevo.host') === 'smtp-relay.brevo.com'
            && config('mail.mailers.kmj_brevo.port') === 465
            && config('mail.mailers.kmj_brevo.timeout') === 10
            && config('mail.mailers.kmj_brevo.url') === null
            && config('mail.mailers.kmj_brevo.verify_peer', true) === true
            && config('mail.mailers.kmj_brevo.kmj_activation_confirmed') === true
            && $credentials !== null;
    }

    public function mailer(string $profile): ?string
    {
        if (! $this->ready($profile)) {
            return null;
        }

        return match ($profile) {
            'loopback' => 'kmj_native_loopback',
            'brevo' => 'kmj_brevo',
            default => null,
        };
    }

    /** @return array<string, string> */
    public function queueAttributes(): array
    {
        return Schema::hasColumn('kmj_mail_messages', 'native_smtp_profile')
            ? ['native_smtp_profile' => $this->activeProfile()]
            : [];
    }

    /** @return array<string, mixed> */
    public function snapshot(User $actor): array
    {
        $this->owner->require($actor);
        $row = $this->installed() ? DB::table('kmj_native_smtp_settings')->where('id', 1)->first() : null;

        return [
            'installed' => $this->installed(),
            'active' => $this->activeProfile(),
            'loopback_ready' => $this->ready('loopback'),
            'brevo_ready' => $this->ready('brevo'),
            'brevo_credentials_stored' => $row !== null && is_string($row->brevo_login_ciphertext) && is_string($row->brevo_password_ciphertext),
            'brevo_server_approved' => config('mail.mailers.kmj_brevo.kmj_activation_confirmed') === true,
            'tested_profile' => $row->tested_profile ?? null,
            'tested_at' => $row->tested_at ?? null,
            'sender' => (string) config('mail.from.address', ''),
        ];
    }

    public function test(User $actor, string $profile): void
    {
        $this->owner->require($actor);
        abort_unless($this->installed(), 503);
        $mailer = $this->mailer($profile);
        $from = (string) config('mail.from.address', '');
        if ($mailer === null || ! filter_var($from, FILTER_VALIDATE_EMAIL)
            || ! str_ends_with(strtolower($from), '@kmjtechno.com')) {
            throw ValidationException::withMessages(['profile' => 'The pinned SMTP profile or verified domain sender is not ready.']);
        }

        $fingerprint = $this->fingerprint($profile);
        // The explicit owner action sends one fixed test to that verified owner,
        // never to an arbitrary recipient and never includes mailbox content.
        try {
            $receipt = $this->send($profile, (string) $actor->email, new NativeExternalMailMessage(
                '[KMJ SMTP TEST] Transport acceptance',
                'This is an owner-requested KMJ Mail transport test. Receipt in your mailbox must be checked separately.',
                $from,
            ));
            if ($receipt === null) {
                throw new \RuntimeException('No SMTP submission receipt');
            }
        } catch (Throwable) {
            $this->audit($actor, 'kmj_native_smtp_test', 'failed', $profile);
            throw ValidationException::withMessages(['profile' => 'SMTP submission failed. No transport setting was activated.']);
        }

        DB::table('kmj_native_smtp_settings')->upsert([[
            'id' => 1,
            'tested_profile' => $profile,
            'tested_fingerprint' => $fingerprint,
            'tested_by' => (int) $actor->getKey(),
            'tested_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ]], ['id'], ['tested_profile', 'tested_fingerprint', 'tested_by', 'tested_at', 'updated_at']);
        $this->audit($actor, 'kmj_native_smtp_test', 'accepted', $profile);
    }

    public function activate(User $actor, string $profile): void
    {
        $this->owner->require($actor);
        abort_unless($this->installed(), 503);
        if (! $this->ready($profile)) {
            throw ValidationException::withMessages(['profile' => 'SMTP profile is not ready.']);
        }

        DB::transaction(function () use ($actor, $profile): void {
            $row = DB::table('kmj_native_smtp_settings')->where('id', 1)->lockForUpdate()->first();
            if ($row === null || $row->tested_profile !== $profile
                || (int) $row->tested_by !== (int) $actor->getKey()
                || ! is_string($row->tested_fingerprint)
                || ! hash_equals($row->tested_fingerprint, $this->fingerprint($profile))
                || DB::table('kmj_native_smtp_settings')->where('id', 1)
                    ->where('tested_at', '>=', now()->subMinutes(15))->doesntExist()) {
                throw ValidationException::withMessages(['profile' => 'Run a successful test on this exact profile within the last 15 minutes.']);
            }
            DB::table('kmj_native_smtp_settings')->where('id', 1)->update([
                'active_profile' => $profile,
                'tested_profile' => null,
                'tested_fingerprint' => null,
                'tested_by' => null,
                'tested_at' => null,
                'updated_at' => now(),
            ]);
            $this->audit($actor, 'kmj_native_smtp_activate', 'success', $profile);
        });
    }

    public function pause(User $actor): void
    {
        $this->owner->require($actor);
        abort_unless($this->installed(), 503);
        DB::table('kmj_native_smtp_settings')->upsert([[
            'id' => 1,
            'active_profile' => 'paused',
            'tested_profile' => null,
            'tested_fingerprint' => null,
            'tested_by' => null,
            'tested_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ]], ['id'], ['active_profile', 'tested_profile', 'tested_fingerprint', 'tested_by', 'tested_at', 'updated_at']);
        $this->audit($actor, 'kmj_native_smtp_pause', 'success', 'paused');
    }

    public function saveBrevoCredentials(User $actor, mixed $login, mixed $password): void
    {
        $this->owner->require($actor);
        abort_unless($this->installed(), 503);
        if (! is_string($login) || ! is_string($password)
            || $login === '' || $password === '' || strlen($login) > 254 || strlen($password) > 1024
            || preg_match('/[\x00-\x20\x7f]/', $login) === 1
            || preg_match('/[\x00-\x20\x7f]/', $password) === 1) {
            throw new \InvalidArgumentException('Invalid SMTP credentials.');
        }

        DB::transaction(function () use ($actor, $login, $password): void {
            $row = DB::table('kmj_native_smtp_settings')->where('id', 1)->lockForUpdate()->first();
            if ($row !== null && $row->active_profile === 'brevo') {
                throw new \InvalidArgumentException('Pause or select local SMTP before rotating remote credentials.');
            }
            DB::table('kmj_native_smtp_settings')->upsert([[
                'id' => 1,
                'brevo_login_ciphertext' => Crypt::encryptString($login),
                'brevo_password_ciphertext' => Crypt::encryptString($password),
                'tested_profile' => null,
                'tested_fingerprint' => null,
                'tested_by' => null,
                'tested_at' => null,
                'created_at' => now(),
                'updated_at' => now(),
            ]], ['id'], ['brevo_login_ciphertext', 'brevo_password_ciphertext', 'tested_profile', 'tested_fingerprint', 'tested_by', 'tested_at', 'updated_at']);
            $this->audit($actor, 'kmj_native_smtp_credentials_saved', 'saved_unverified', 'brevo');
        });
    }

    /** @return array{username:string,password:string}|null */
    private function brevoCredentials(): ?array
    {
        $row = $this->installed() ? DB::table('kmj_native_smtp_settings')->where('id', 1)->first() : null;
        if ($row !== null && ($row->brevo_login_ciphertext !== null || $row->brevo_password_ciphertext !== null)) {
            if (! is_string($row->brevo_login_ciphertext) || ! is_string($row->brevo_password_ciphertext)) {
                return null;
            }
            try {
                $username = Crypt::decryptString($row->brevo_login_ciphertext);
                $password = Crypt::decryptString($row->brevo_password_ciphertext);
            } catch (DecryptException) {
                return null;
            }
        } else {
            $username = config('mail.mailers.kmj_brevo.username');
            $password = config('mail.mailers.kmj_brevo.password');
        }

        return is_string($username) && trim($username) !== ''
            && is_string($password) && trim($password) !== ''
            ? ['username' => $username, 'password' => $password] : null;
    }

    public function send(string $profile, string $recipient, NativeExternalMailMessage $message): ?SentMessage
    {
        $mailer = $this->mailer($profile);
        if ($mailer === null) {
            throw new \RuntimeException('SMTP route is unavailable.');
        }
        if ($profile === 'loopback') {
            return Mail::mailer($mailer)->to($recipient)->send($message);
        }

        $credentials = $this->brevoCredentials();
        if ($credentials === null) {
            throw new \RuntimeException('SMTP credentials unavailable.');
        }

        // Build an isolated instance for every remote submission. Never
        // overwrite global transactional mail configuration or cache a secret.
        return Mail::build([
            'name' => 'kmj_native_brevo_runtime',
            'transport' => 'smtp',
            'scheme' => 'smtps',
            'host' => 'smtp-relay.brevo.com',
            'port' => 465,
            'timeout' => 10,
            'local_domain' => 'kmjtechno.com',
            'verify_peer' => true,
            ...$credentials,
        ])->to($recipient)->send($message);
    }

    private function fingerprint(string $profile): string
    {
        $name = $profile === 'loopback' ? 'kmj_native_loopback' : 'kmj_brevo';

        return hash_hmac('sha256', json_encode([
            config('mail.mailers.'.$name),
            config('mail.from.address'),
            $profile === 'brevo' ? $this->brevoCredentials() : null,
        ], JSON_THROW_ON_ERROR), (string) config('app.key'));
    }

    private function audit(User $actor, string $action, string $outcome, string $profile): void
    {
        OperatorActionAudit::query()->create([
            'actor_user_id' => (int) $actor->getKey(),
            'action' => $action,
            'outcome' => $outcome,
            'metadata' => ['profile' => $profile],
        ]);
    }
}
