<?php

declare(strict_types=1);

namespace App\Services\Auth;

use DomainException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;

/**
 * Google sign-in with the authorization-code flow and PKCE, no extra package. Only identity fields
 * are read (subject id, verified email, name); no Google API access is requested or stored.
 */
final class GoogleSignIn
{
    private const AUTHORIZE = 'https://accounts.google.com/o/oauth2/v2/auth';

    private const TOKEN = 'https://oauth2.googleapis.com/token';

    private const USERINFO = 'https://openidconnect.googleapis.com/v1/userinfo';

    private const SESSION_KEY = 'google_signin';

    public function enabled(): bool
    {
        $id = config('services.google_signin.client_id');
        $secret = config('services.google_signin.client_secret');

        return is_string($id) && trim($id) !== '' && is_string($secret) && trim($secret) !== '';
    }

    public function redirectUri(): string
    {
        return route('auth.google.callback');
    }

    public function authorizationUrl(Request $request): string
    {
        $state = bin2hex(random_bytes(16));
        $verifier = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
        $request->session()->put(self::SESSION_KEY, [
            'state' => $state,
            'verifier' => $verifier,
            'at' => time(),
        ]);

        return self::AUTHORIZE.'?'.http_build_query([
            'client_id' => (string) config('services.google_signin.client_id'),
            'redirect_uri' => $this->redirectUri(),
            'response_type' => 'code',
            'scope' => 'openid email profile',
            'state' => $state,
            'code_challenge' => rtrim(strtr(base64_encode(hash('sha256', $verifier, true)), '+/', '-_'), '='),
            'code_challenge_method' => 'S256',
            'prompt' => 'select_account',
        ], '', '&', PHP_QUERY_RFC3986);
    }

    /**
     * @return array{sub: string, email: string, name: string}
     *
     * @throws DomainException with a short machine code; never shown with provider details
     */
    public function profileFromCallback(Request $request): array
    {
        if (! $this->enabled()) {
            throw new DomainException('GOOGLE_SIGNIN_DISABLED');
        }

        $pending = $request->session()->pull(self::SESSION_KEY);
        if (! is_array($pending) || ! is_string($pending['state'] ?? null) || ! is_string($pending['verifier'] ?? null)
            || ! is_int($pending['at'] ?? null) || time() - $pending['at'] > 600) {
            throw new DomainException('GOOGLE_STATE_MISSING');
        }

        $state = $request->query('state');
        if (! is_string($state) || ! hash_equals($pending['state'], $state)) {
            throw new DomainException('GOOGLE_STATE_MISMATCH');
        }

        $code = $request->query('code');
        if ($request->query('error') !== null || ! is_string($code) || $code === '' || strlen($code) > 2048) {
            throw new DomainException('GOOGLE_AUTH_DECLINED');
        }

        $token = Http::asForm()->timeout(10)->post(self::TOKEN, [
            'code' => $code,
            'client_id' => (string) config('services.google_signin.client_id'),
            'client_secret' => (string) config('services.google_signin.client_secret'),
            'redirect_uri' => $this->redirectUri(),
            'grant_type' => 'authorization_code',
            'code_verifier' => $pending['verifier'],
        ]);
        $accessToken = $token->successful() ? $token->json('access_token') : null;
        if (! is_string($accessToken) || $accessToken === '') {
            throw new DomainException('GOOGLE_TOKEN_REJECTED');
        }

        $info = Http::withToken($accessToken)->timeout(10)->get(self::USERINFO);
        if (! $info->successful()) {
            throw new DomainException('GOOGLE_USERINFO_FAILED');
        }

        $sub = $info->json('sub');
        $email = $info->json('email');
        $verified = $info->json('email_verified');
        $name = $info->json('name');

        if (! is_string($sub) || $sub === '' || strlen($sub) > 191
            || ! is_string($email) || filter_var($email, FILTER_VALIDATE_EMAIL) === false || strlen($email) > 254) {
            throw new DomainException('GOOGLE_PROFILE_INVALID');
        }
        if ($verified !== true && $verified !== 'true') {
            throw new DomainException('GOOGLE_EMAIL_NOT_VERIFIED');
        }

        $name = is_string($name) ? trim(Str::limit(strip_tags($name), 120, '')) : '';

        return [
            'sub' => $sub,
            'email' => strtolower($email),
            'name' => $name !== '' ? $name : Str::before($email, '@'),
        ];
    }
}
