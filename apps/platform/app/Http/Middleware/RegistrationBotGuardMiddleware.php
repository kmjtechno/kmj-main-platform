<?php

namespace App\Http\Middleware;

use App\Services\Auth\RegistrationBotGuard;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\Response;

/** Runs only on the public POST /register, after the signup throttle. */
final class RegistrationBotGuardMiddleware
{
    public function __construct(private readonly RegistrationBotGuard $guard) {}

    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->isMethod('POST') || ! $request->is('register') || ! $this->guard->enabled()) {
            return $next($request);
        }

        $reason = $this->guard->rejectionReason($request);
        if ($reason === null) {
            return $next($request);
        }

        // No email, name or plaintext IP in the log: only the reason and a hashed address.
        Log::notice('registration.bot_guard_rejected', [
            'reason' => $reason,
            'ip_hash' => substr(hash('sha256', (string) $request->ip()), 0, 16),
        ]);

        throw ValidationException::withMessages([
            'registration' => 'We could not verify this form. Please reload the page and try again.',
        ]);
    }
}
