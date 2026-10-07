# KMJ CodeBridge Owner/Admin — operator activation

Status: implementation PR only. The live account remains Professional until verified provisioning and signed activation succeed.

1. Complete CI and security review; merge and deploy the reviewed commit through the approved release process with rollback.
2. Sign in to Main Platform's existing operator screen as a verified platform owner with an enrolled passkey; confirm the account password when prompted. Do not create duplicate ChatGPT apps, devices, or repositories.
3. At /operator/kslp, identify the correct active KMJ_CODEBRIDGE Professional license and customer/tenant. Enter an audit reason of at least 10 characters; choose Activate Owner/Admin for that license, then confirm. Do not select another customer's license.
4. The server-side transaction validates owner privileges, license and tenant binding, product, active period, exact codebridge.owner_admin plan policy, and writes an audit event. It changes only the plan and sequence. Device enrollment and activation records remain intact. Repeated invocation is idempotent.
5. The plan policy enables read/write/execute, with a signed device ceiling of 2,147,483,647 and a signed concurrency ceiling of 16. These are upper limits, not unlimited CPU, RAM, storage, user permission, subscription, or external API quota.
6. Obtain a genuine Ed25519 device-bound entitlement using the existing device credential and approved Main Platform signer. Follow kmj-codebridge/docs/OWNER-SIGNED-ACTIVATION.md for the private Linux opt-in activation helper, config backup, agent restart and verification. Never paste keys, JWS leases or device credentials into GitHub or ChatGPT.
7. Verify live execution_capacity, device list, signed-license status, audit event, project permissions, update/rollback health and quality gates. If activation, renewal or checks fail, preserve the original configuration and report NOT ACTIVE; do not forge claims.

The operator action requires authentication, verified email, recent password confirmation and PlatformOwnerAccess (owner role plus enrolled passkey). API callers receive no-store JSON; Inertia operators receive a redirect. No purchase or license charge is created by this provisioning action.
