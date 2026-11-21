<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use App\Models\AiModelToken;
use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Symfony\Component\HttpFoundation\Response;

/**
 * Bearer authentication for the ModelFabric endpoint: hash lookup, expiry and revocation checks and a
 * per-token rate limit. The token only identifies an organization; it cannot widen routing rules.
 */
final class AuthenticateModelFabricToken
{
    public const PER_MINUTE = 60;

    public function handle(Request $request, Closure $next): Response
    {
        $plain = (string) $request->bearerToken();
        if ($plain === '' || ! str_starts_with($plain, AiModelToken::PREFIX) || strlen($plain) > 128) {
            return $this->error(401, 'invalid_token', 'Missing or invalid ModelFabric token.');
        }

        $token = AiModelToken::query()->where('token_hash', AiModelToken::hash($plain))->first();
        if (! $token instanceof AiModelToken || ! $token->isUsable()) {
            return $this->error(401, 'invalid_token', 'Missing or invalid ModelFabric token.');
        }

        $key = 'modelfabric-token:'.$token->id;
        if (RateLimiter::tooManyAttempts($key, self::PER_MINUTE)) {
            return $this->error(429, 'rate_limited', 'Token rate limit reached.')
                ->withHeaders(['Retry-After' => (string) RateLimiter::availableIn($key)]);
        }
        RateLimiter::hit($key, 60);

        $token->last_used_at = now();
        $token->save();
        $request->attributes->set('modelfabric_token', $token);

        return $next($request);
    }

    private function error(int $status, string $code, string $message): JsonResponse
    {
        return response()->json(['error' => ['message' => $message, 'type' => 'modelfabric_error', 'code' => $code]], $status);
    }
}
