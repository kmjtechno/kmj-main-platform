<?php

declare(strict_types=1);

namespace App\Services\Auth;

use Illuminate\Contracts\Encryption\DecryptException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use JsonException;

/**
 * Invisible anti-bot checks for public signup. A hidden field real users never fill, plus an encrypted
 * time-stamped token that can be used once. It lowers automated signups; it does not prove a human.
 */
final class RegistrationBotGuard
{
    public function enabled(): bool
    {
        return (bool) config('registration.bot_guard.enabled', true);
    }

    public function issueToken(): string
    {
        return Crypt::encryptString(json_encode([
            'n' => bin2hex(random_bytes(16)),
            't' => time(),
        ], JSON_THROW_ON_ERROR));
    }

    /** Null when the submission passes; otherwise a short machine reason (never shown to the visitor). */
    public function rejectionReason(Request $request): ?string
    {
        $honeypot = (string) config('registration.bot_guard.honeypot_field', 'website_url');
        $tokenField = (string) config('registration.bot_guard.token_field', 'kmj_form_token');

        if (trim((string) $request->input($honeypot, '')) !== '') {
            return 'honeypot_filled';
        }

        $token = $request->input($tokenField);
        if (! is_string($token) || $token === '' || strlen($token) > 2048) {
            return 'token_missing';
        }

        try {
            $payload = json_decode(Crypt::decryptString($token), true, 4, JSON_THROW_ON_ERROR);
        } catch (DecryptException|JsonException) {
            return 'token_invalid';
        }

        if (! is_array($payload) || ! is_string($payload['n'] ?? null) || ! is_int($payload['t'] ?? null)
            || ! preg_match('/\A[a-f0-9]{32}\z/D', $payload['n'])) {
            return 'token_invalid';
        }

        $age = time() - $payload['t'];
        if ($age < (int) config('registration.bot_guard.min_seconds', 3)) {
            return 'submitted_too_fast';
        }
        $max = (int) config('registration.bot_guard.max_seconds', 7200);
        if ($age > $max) {
            return 'token_expired';
        }

        // One use per token: a bot cannot replay a single valid token for many signups.
        if (! Cache::add('registration-bot-guard:'.$payload['n'], 1, $max)) {
            return 'token_replayed';
        }

        return null;
    }
}
