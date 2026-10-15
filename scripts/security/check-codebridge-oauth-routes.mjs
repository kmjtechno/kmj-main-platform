#!/usr/bin/env node
// Static defense-in-depth gate for KMJ CodeBridge's customer OAuth routes.
// This is NOT a replacement for PKCE, session, CSRF, tenant and token tests.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const ROUTES_PATH = path.join(root, "apps/platform/routes/codebridge-oauth.php");

function occurrences(source, re) {
  return [...source.matchAll(re)].length;
}

export function auditOAuthRoutes(source) {
  if (typeof source !== "string" || source.length < 500) {
    throw new Error("CODEBRIDGE_OAUTH_ROUTE_SOURCE_INVALID");
  }
  const errors = [];

  // A registration/authorization route must use actual login + verified
  // middleware; never silently log in the first user as an "admin".
  const protectedGroup = /Route::middleware\(\s*\[\s*['"]auth['"]\s*,\s*['"]verified['"]\s*\]\s*\)->group\s*\(/;
  const groupIndex = source.search(protectedGroup);
  const authorizeIndex = source.search(/Route::get\(\s*['"]oauth\/authorize['"]/);
  if (groupIndex < 0 || authorizeIndex < groupIndex) {
    errors.push("AUTHORIZATION_MIDDLEWARE_MISSING");
  }

  const required = [
    [/Route::get\(\s*['"]oauth\/authorize['"]/g, "AUTHORIZATION_GET_ROUTE_COUNT"],
    [/Route::post\(\s*['"]oauth\/authorize['"]/g, "AUTHORIZATION_POST_ROUTE_COUNT"],
    [/Route::post\(\s*['"]oauth\/token['"]/g, "TOKEN_ROUTE_COUNT"],
  ];
  for (const [pattern, code] of required) {
    if (occurrences(source, pattern) !== 1) errors.push(code);
  }

  if (!source.includes("$server->validateAuthorization($request->query())"))
    errors.push("AUTHORIZATION_REQUEST_NOT_VALIDATED");
  if (!source.includes("$server->approve($pending,"))
    errors.push("CONSENT_APPROVAL_MISSING");
  if (!source.includes("$server->deny($pending)"))
    errors.push("CONSENT_DENIAL_MISSING");
  if (!source.includes("$request->session()->pull('codebridge_oauth.'"))
    errors.push("CONSENT_SESSION_BINDING_MISSING");

  const forbidden = [
    // Browser/desktop convenience must never create impersonation.
    [/\bauth\s*\(\s*\)\s*->\s*(?:login|loginUsingId)\s*\(/i, "IMPLICIT_USER_LOGIN"],
    [/\bAuth\s*::\s*(?:login|loginUsingId)\s*\(/i, "IMPLICIT_USER_LOGIN"],
    [/\bAuth\s*::\s*guard\([^)]*\)\s*->\s*(?:login|loginUsingId)\s*\(/i, "IMPLICIT_USER_LOGIN"],
    [/\bRoute::(?:any|match)\s*\(\s*['"]oauth\/(?:token|authorize)['"]/i, "UNRESTRICTED_OAUTH_ROUTE"],
    [/\bDB\s*::\s*table\s*\(\s*['"]codebridge_oauth_codes['"]\s*\)\s*->\s*insert\s*\(/i, "DIRECT_CODE_INSERTION"],
    [/\bOAuthCore\s*::\s*(?:secret|hashSecret)\s*\(/i, "UNREVIEWED_TOKEN_MINTING"],
    [/(?:^|\W)cb_super_admin(?:\W|$)/i, "UNREVIEWED_SUPERADMIN_CLIENT"],
  ];
  for (const [pattern, code] of forbidden) {
    if (pattern.test(source)) errors.push(code);
  }
  return [...new Set(errors)];
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  // One fixed path only. Do not accept arbitrary callers' source paths,
  // print PHP source, or leak OAuth client/user/token data.
  const failures = auditOAuthRoutes(fs.readFileSync(ROUTES_PATH, "utf8"));
  if (failures.length) {
    console.error("CODEBRIDGE_OAUTH_ROUTE_GUARD=FAIL " + failures.join(","));
    process.exitCode = 1;
  } else {
    console.log("CODEBRIDGE_OAUTH_ROUTE_GUARD=PASS");
  }
}
