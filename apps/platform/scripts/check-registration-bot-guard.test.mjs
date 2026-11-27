import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

void test('register form carries a hidden token and an invisible honeypot', () => {
    const page = read('resources/js/pages/auth/register.tsx');
    assert.match(page, /name="kmj_form_token"/);
    assert.match(page, /name="website_url"/);
    assert.match(page, /aria-hidden="true"/);
    assert.match(page, /tabIndex=\{-1\}/);
    assert.match(page, /errors\.registration/);
});

void test('guard is server-side, one-use, time-bound and uses no third party', () => {
    const guard = read('app/Services/Auth/RegistrationBotGuard.php');
    assert.match(guard, /Crypt::encryptString/);
    assert.match(guard, /Cache::add\('registration-bot-guard:'/);
    assert.match(guard, /submitted_too_fast/);
    assert.match(guard, /token_expired/);
    assert.match(guard, /honeypot_filled/);
    assert.doesNotMatch(guard, /Http::|recaptcha|turnstile|hcaptcha/i);
});

void test('guard logs only a reason and a hashed address, and runs after the throttle on /register only', () => {
    const mw = read('app/Http/Middleware/RegistrationBotGuardMiddleware.php');
    assert.match(mw, /ip_hash/);
    assert.doesNotMatch(mw, /'email'\s*=>|'name'\s*=>/);
    assert.match(mw, /is\('register'\)/);
    const bootstrap = read('bootstrap/app.php');
    assert.ok(
        bootstrap.indexOf('ThrottlePublicRegistration::class,') <
            bootstrap.indexOf('RegistrationBotGuardMiddleware::class,'),
    );
});

void test('the guard is on by default and only switched off for the test suite', () => {
    assert.match(
        read('config/registration.php'),
        /env\('REGISTRATION_BOT_GUARD', true\)/,
    );
    assert.match(read('phpunit.xml'), /REGISTRATION_BOT_GUARD" value="false"/);
});
