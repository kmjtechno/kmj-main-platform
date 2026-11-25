# KMJ Mail Enterprise — JMAP foundation

See issue #1183 for upstream register, license gates and full acceptance roadmap.

This change implements a pure read-only JMAP session validator and Mailbox/get request builder. It pins the intended production HTTPS origin and API path, accepts only the authenticated session's primary personal mail account and rejects foreign endpoints, insecure URLs and shared accounts. It performs no HTTP requests, authentication, provisioning, migration, SMTP, DNS, configuration, or UI wiring.

References: RFC 8620 (JMAP core), RFC 8621 (JMAP mail), https://github.com/stalwartlabs/stalwart/tree/v1.2.0 .

The actual Stalwart API URL, capability response and account ID format must be qualified before wiring; this intentionally strict production policy may reject a pilot URL or additional valid JMAP identifiers. Do not weaken the origin policy to permit arbitrary redirects or arbitrary hosts. The future server transport must separately validate TLS, reject redirects, use a user-scoped secret, enforce owner authorization, bound response sizes and validate method response/account IDs. This contract alone is not proof of live delivery or security.

No upstream code copied. Community engine remains separate; licenses and notices preserved. No Enterprise-only feature use without license. No new package dependency. Existing outbound and inbound paths are untouched.

Next: verify isolated PostgreSQL wizard, mailbox login, authenticated JMAP discovery with synthetic data, and then integration tests for real response, read-only Inbox and per-user identity. Public MX activation only after independent external SMTP, anti-relay, sender authentication, queue/recovery and owner gates.
