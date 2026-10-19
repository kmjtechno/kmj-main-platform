import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (relative) =>
    readFileSync(new URL(relative, import.meta.url), 'utf8');
const routes = read('../routes/codebridge-oauth.php');
const server = read('../app/Services/CodeBridge/OAuth/OAuthServer.php');

function audit(source, authority) {
    const issues = [];

    const protectedGroup = source.indexOf(
        "Route::middleware(['auth', 'verified'])->group",
    );
    const authorizeGet = source.indexOf("Route::get('oauth/authorize'");
    const authorizePost = source.indexOf("Route::post('oauth/authorize'");

    if (
        protectedGroup < 0 ||
        authorizeGet <= protectedGroup ||
        authorizePost <= protectedGroup
    ) {
        issues.push('UNVERIFIED_OAUTH_CONSENT');
    }

    for (const [pattern, label] of [
        [/Route::get\('oauth\/authorize'/g, 'AUTHORIZE_GET_COUNT'],
        [/Route::post\('oauth\/authorize'/g, 'AUTHORIZE_POST_COUNT'],
        [/Route::post\('oauth\/token'/g, 'TOKEN_POST_COUNT'],
    ]) {
        if ((source.match(pattern) ?? []).length !== 1) {
            issues.push(label);
        }
    }

    for (const [must, label] of [
        ['$server->validateAuthorization($request->query())', 'NO_VALIDATION'],
        ["$request->session()->pull('codebridge_oauth.'", 'NO_SESSION_CONSENT'],
        ["$pending['consenting_user_id']", 'NO_USER_CONSENT_BINDING'],
        ['$server->approve($pending,', 'NO_USER_APPROVAL'],
        ['$server->deny($pending)', 'NO_DENIAL'],
    ]) {
        if (!source.includes(must)) {
            issues.push(label);
        }
    }

    for (const [pattern, label] of [
        [/\bauth\(\)\s*->\s*(?:login|loginUsingId)\s*\(/i, 'IMPLICIT_LOGIN'],
        [/\bAuth::(?:login|loginUsingId)\s*\(/i, 'IMPLICIT_LOGIN'],
        [
            /\bAuth::guard\([^)]*\)\s*->\s*(?:login|loginUsingId)\s*\(/i,
            'IMPLICIT_LOGIN',
        ],
        [
            /\bRoute::(?:any|match)\s*\(\s*['"]oauth\/(?:authorize|token)['"]/i,
            'UNRESTRICTED_OAUTH_ROUTE',
        ],
        [/\bcb_super_admin\b/i, 'SUPERADMIN_BYPASS_CLIENT'],
    ]) {
        if (pattern.test(source)) {
            issues.push(label);
        }
    }

    if (
        (authority.match(/function\s+validateAuthorization\s*\(/g) ?? [])
            .length !== 1
    ) {
        issues.push('AUTH_VALIDATOR_COUNT');
    }

    for (const [must, label] of [
        ['$this->resolveClient($clientId)', 'CLIENT_NOT_VALIDATED'],
        [
            'OAuthCore::redirectMatches($registered, $redirect)',
            'REDIRECT_NOT_VALIDATED',
        ],
        [
            "OAuthCore::isValidChallenge($query['code_challenge'])",
            'CHALLENGE_NOT_VALIDATED',
        ],
        ['OAuthCore::parseScopes(', 'SCOPES_NOT_VALIDATED'],
        ['OAuthCore::verifyPkce(', 'PKCE_NOT_VERIFIED'],
        ['public function approve(', 'APPROVAL_MISSING'],
    ]) {
        if (!authority.includes(must)) {
            issues.push(label);
        }
    }

    if (/\bcb_super_admin\b/i.test(authority)) {
        issues.push('SUPERADMIN_BYPASS_CLIENT');
    }

    return [...new Set(issues)];
}

void test('Main Platform OAuth consent is guarded', () => {
    assert.deepEqual(audit(routes, server), []);
});

void test('silent owner login and admin client injection fail', () => {
    for (const malicious of [
        'auth()->login($admin);',
        'Auth::loginUsingId(1);',
        "Auth::guard('web')->login($admin);",
        "$clientId = 'cb_super_admin';",
    ]) {
        assert.notDeepEqual(audit(routes + '\n' + malicious, server), []);
    }
});

void test('wildcard or duplicate OAuth handlers cannot pass the guard', () => {
    for (const malicious of [
        "Route::any('oauth/token', function () {});",
        "Route::match(['GET'], 'oauth/authorize', function () {});",
        "Route::get('oauth/authorize', function () {});",
    ]) {
        assert.notDeepEqual(audit(routes + '\n' + malicious, server), []);
    }
});

void test('missing consent or session binding fails the guard', () => {
    for (const required of [
        "Route::middleware(['auth', 'verified'])->group",
        '$server->validateAuthorization($request->query())',
        "$request->session()->pull('codebridge_oauth.'",
        "$pending['consenting_user_id']",
        '$server->approve($pending,',
    ]) {
        assert.notDeepEqual(
            audit(routes.replace(required, 'REMOVED_GUARD'), server),
            [],
        );
    }
});

void test('OAuth server cannot omit PKCE/client/redirect validation', () => {
    for (const required of [
        '$this->resolveClient($clientId)',
        'OAuthCore::redirectMatches($registered, $redirect)',
        "OAuthCore::isValidChallenge($query['code_challenge'])",
        'OAuthCore::verifyPkce(',
    ]) {
        assert.notDeepEqual(
            audit(routes, server.replace(required, 'REMOVED_GUARD')),
            [],
        );
    }
});

void test('a duplicate permissive authorization validator is rejected', () => {
    const injected = [
        server,
        'public function validateAuthorization(array $query) { return []; }',
    ].join('\n');
    assert.ok(audit(routes, injected).includes('AUTH_VALIDATOR_COUNT'));
});
