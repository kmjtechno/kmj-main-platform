import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

void test('google sign-in uses code flow with PKCE and state, and reads identity fields only', () => {
    const svc = read('app/Services/Auth/GoogleSignIn.php');
    assert.match(svc, /'code_challenge_method' => 'S256'/);
    assert.match(svc, /hash_equals\(\$pending\['state'\]/);
    assert.match(svc, /'scope' => 'openid email profile'/);
    assert.match(svc, /GOOGLE_EMAIL_NOT_VERIFIED/);
    assert.doesNotMatch(svc, /drive|gmail|calendar/i);
});

void test('google login never bypasses a passkey or two-factor and revokes a pre-registered password', () => {
    const ctl = read('app/Http/Controllers/Auth/GoogleAuthController.php');
    assert.match(ctl, /two_factor_confirmed_at/);
    assert.match(ctl, /passkeys/);
    assert.match(ctl, /Hash::make\(Str::random\(48\)\)/);
    assert.doesNotMatch(ctl, /\$request->(input|query)\('email'\)/);
});

void test('the button is hidden unless server credentials exist and secrets never reach the browser', () => {
    assert.match(
        read('resources/js/components/google-signin-button.tsx'),
        /google_signin_available !== true/,
    );
    const inertia = read('app/Http/Middleware/HandleInertiaRequests.php');
    assert.match(
        inertia,
        /'google_signin_available' => app\(GoogleSignIn::class\)->enabled\(\)/,
    );
    assert.doesNotMatch(inertia, /client_secret/);
    assert.match(read('config/services.php'), /GOOGLE_OAUTH_CLIENT_SECRET/);
});

void test('profile details are collected after sign-in on a verified, authenticated route', () => {
    const routes = read('routes/google-auth.php');
    assert.match(routes, /\['auth', 'verified'\][\s\S]*onboarding\/profile/);
    assert.match(
        read('resources/js/pages/auth/complete-profile.tsx'),
        /name="phone"/,
    );
});

void test('google sign-in routes use their own named rate limiters, not the shared numeric bucket', () => {
    const routes = read('routes/google-auth.php');
    assert.match(routes, /throttle:google-signin/);
    assert.match(routes, /throttle:onboarding-profile/);
    assert.doesNotMatch(routes, /throttle:\d+,\d+/);
    const provider = read('app/Providers/FortifyServiceProvider.php');
    assert.match(provider, /RateLimiter::for\('google-signin'/);
    assert.match(provider, /RateLimiter::for\('onboarding-profile'/);
});
