import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  auditOAuthRoutes,
  auditOAuthServer,
  ROUTES_PATH,
  SERVER_PATH,
} from "../scripts/security/check-codebridge-oauth-routes.mjs";

const trusted = fs.readFileSync(ROUTES_PATH, "utf8");
const trustedServer = fs.readFileSync(SERVER_PATH, "utf8");

test("committed CodeBridge OAuth routes enforce identity, PKCE and user consent", () => {
  assert.deepEqual(auditOAuthRoutes(trusted), []);
});

test("unauthenticated first-user login injection is denied", () => {
  for (const injection of [
    "auth()->login($admin);",
    "Auth::loginUsingId(1);",
    "Auth::guard('web')->login($admin);",
  ]) {
    const altered = trusted + "\n" + injection;
    assert.ok(auditOAuthRoutes(altered).includes("IMPLICIT_USER_LOGIN"));
  }
});

test("wildcard OAuth handlers and additional code or token issuers are denied", () => {
  const scenarios = [
    ["Route::any('oauth/token', function () {});", "UNRESTRICTED_OAUTH_ROUTE"],
    ["Route::any('oauth/authorize', function () {});", "UNRESTRICTED_OAUTH_ROUTE"],
    ["DB::table('codebridge_oauth_codes')->insert([]);", "DIRECT_CODE_INSERTION"],
    ["OAuthCore::secret();", "UNREVIEWED_TOKEN_MINTING"],
    ["$clientId = 'cb_super_admin';", "UNREVIEWED_SUPERADMIN_CLIENT"],
    ["Route::get('oauth/authorize', function () {});", "AUTHORIZATION_GET_ROUTE_COUNT"],
  ];
  for (const [source, failure] of scenarios) {
    assert.ok(auditOAuthRoutes(trusted + "\n" + source).includes(failure), failure);
  }
});

test("authorization approval cannot silently bypass verified middleware and consent", () => {
  const scenarios = [
    [
      trusted.replace("Route::middleware(['auth', 'verified'])->group", "Route::group"),
      "AUTHORIZATION_MIDDLEWARE_MISSING",
    ],
    [
      trusted.replace("$server->validateAuthorization($request->query())", "[]"),
      "AUTHORIZATION_REQUEST_NOT_VALIDATED",
    ],
    [
      trusted.replace("$server->approve($pending,", "$server->grant($pending,"),
      "CONSENT_APPROVAL_MISSING",
    ],
    [
      trusted.replace("$request->session()->pull('codebridge_oauth.'", "$request->input('request_id'"),
      "CONSENT_SESSION_BINDING_MISSING",
    ],
  ];
  for (const [source, failure] of scenarios) {
    assert.ok(auditOAuthRoutes(source).includes(failure), failure);
  }
});

test("only bounded status codes are returned; no source or user secrets", () => {
  const result = auditOAuthRoutes(trusted + "\nauth()->login($admin);");
  assert.deepEqual(result, ["IMPLICIT_USER_LOGIN"]);
  assert.throws(() => auditOAuthRoutes("short"), /CODEBRIDGE_OAUTH_ROUTE_SOURCE_INVALID/);
});

test("committed OAuth server validates registered clients, redirect, PKCE and scope", () => {
  assert.deepEqual(auditOAuthServer(trustedServer), []);
});

test("duplicate permissive validateAuthorization method cannot pass guard", () => {
  const duplicate = trustedServer + [
    "public function validateAuthorization(array $query) {",
    "  // ULTIMATE SUPER ADMIN BYPASS",
    "  return [];",
    "}",
  ].join("\n");
  assert.ok(auditOAuthServer(duplicate).includes("AUTHORIZATION_VALIDATOR_COUNT"));
  assert.ok(auditOAuthServer(duplicate).includes("SUPERADMIN_BYPASS_FORBIDDEN"));
});

test("removing OAuth server identity, redirect or challenge checks is denied", () => {
  const cases = [
    ["$this->resolveClient($clientId)", "CLIENT_REGISTRATION_NOT_VALIDATED"],
    ["OAuthCore::redirectMatches($registered, $redirect)", "REDIRECT_NOT_VALIDATED"],
    ["OAuthCore::isValidChallenge($query['code_challenge'])", "PKCE_CHALLENGE_NOT_VALIDATED"],
    ["OAuthCore::verifyPkce(", "PKCE_VERIFIER_NOT_VALIDATED"],
  ];
  for (const [text, code] of cases) {
    const modified = trustedServer.replace(text, "DO_NOT_VALIDATE");
    assert.ok(auditOAuthServer(modified).includes(code), code);
  }
});
