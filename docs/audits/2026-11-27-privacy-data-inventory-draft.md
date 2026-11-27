# Privacy data inventory — DRAFT (2026-11-27)

Status: `PLANNED`. Roadmap section 18 requires, for each personal-data store: owner, purpose, lawful basis, region, retention, processor and deletion method. Legal terms (DPDP and others) must be confirmed by legal review before any compliance claim. This draft only lists where personal-data-like columns exist, found by scanning the migrations (66 files, 28 tables). It can miss tables created outside migrations or columns with other names, and it does not describe data in provider dashboards, mail servers, backups or logs.

Every cell marked TO CONFIRM is an owner or legal decision; Claude has not invented retention periods, lawful bases or regions.

| Table | Category | Personal-data-like columns | Purpose (draft) | Lawful basis | Region | Retention | Processor / deletion method |
|---|---|---|---|---|---|---|---|
| `ai_model_tokens` | Device/product telemetry or catalog metadata | name, token_hash, token_prefix | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `ai_providers` | Device/product telemetry or catalog metadata | name | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_device_credentials` | Device/product telemetry or catalog metadata | device_id, token_hash | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_device_pairings` | Device/product telemetry or catalog metadata | credential_ciphertext, device_code_hash, device_id, device_name, project_name | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_oauth_clients` | Device/product telemetry or catalog metadata | client_name | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_oauth_refresh_tokens` | Device/product telemetry or catalog metadata | token_hash | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_project_assignments` | Device/product telemetry or catalog metadata | device_id, project_name | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_receipt_bindings` | Device/product telemetry or catalog metadata | credential_id, device_id, subject_key | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_receipt_signers` | Device/product telemetry or catalog metadata | credential_id | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_usage_executions` | Device/product telemetry or catalog metadata | subject_key | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_usage_periods` | Device/product telemetry or catalog metadata | subject_key | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_workspace_conversations` | Device/product telemetry or catalog metadata | device_id | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_workspace_jobs` | Device/product telemetry or catalog metadata | device_id | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `codebridge_workspace_tool_proposals` | Device/product telemetry or catalog metadata | device_id | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `commerce_orders` | Commerce evidence | confirmation_reference (payment reference) | Order and entitlement authority | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `customer_profiles` | Customer contact | company, country, phone | Customer onboarding and invoicing | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `job_batches` | Device/product telemetry or catalog metadata | name | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `kmj_mail_external_inbox` | Mail content (external, quarantined) | sender, recipient, subject, body | KMJ Mail inbound pilot | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `kmj_mail_messages` | Mail content | sender, recipient, subject, body | KMJ Mail service | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `omnidesk_activation_bindings` | Device/product telemetry or catalog metadata | device_public_key, device_public_key_fingerprint | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `organizations` | Business account | organization name | Account operation | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `passkeys` | Authentication credential | credential id, public credential, label | Account security | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `password_reset_tokens` | Account security | email, reset token | Account operation | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `payment_gateway_settings` | Provider secrets (encrypted) | encrypted client and webhook secrets | Payment gateway setup | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `products` | Device/product telemetry or catalog metadata | name | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `release_artifacts` | Device/product telemetry or catalog metadata | filename | Product operation (owner to confirm) | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `sessions` | Session telemetry | ip_address, user_agent | Required for sign-in security | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |
| `users` | Account identity | email, name, 2FA secret | Account operation | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM |

## Known deletion capability in the product
Owner Customers has guarded single and batch deletion and a complete private signup-data deletion path (delivery-progress entries from 2026-11-22). Whether those cover every table above, backups, and the vault ciphertexts is NOT verified.

## Known gaps to close before a privacy claim
1. Retention period per category, including backups (daily snapshots and the encrypted vault).
2. Processors list: payment providers, mail provider(s), AI providers, hosting; data region of each.
3. Consent separation: marketing, optional telemetry, required operation data.
4. Export and correction flows for customers (no evidence found).
5. Deletion propagation to backups and to processors.
6. Legal review for India DPDP and any other jurisdiction served.
