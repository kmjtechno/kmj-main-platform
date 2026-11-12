# KMJ CodeBridge owner-only operator receipts (2026-10-27)

Use CodeBridge directly for all **advertised, administrator-approved** profiles and quality gates. For example, `list_project_commands`, `run_project_command`, then `get_job_status` return real execution results. These actions do not expose a generic root shell.

For exact root-only procedures, a separately owner-executed SHA-pinned adapter can record a **redacted, structured** outcome under the authorized project's `work/qa/operator-receipts/` folder. ChatGPT can then use CodeBridge `read_file` or `read_files_batch` on `work/qa/operator-receipts/latest.json` in a later chat; the owner need not paste the entire terminal output. The adapter is not a background channel or automatic ChatGPT wake-up.

The initial fixed profile `gateway-port-verify` runs an immutable copy of the approved default/read-only gateway port inspector. No arbitrary script path, shell, argument vector or `--apply` option is accepted. Raw stdout/stderr are neither stored nor printed. Only explicit, bounded, regex-validated status markers are stored; receipts are **operator execution evidence, not production approval or independently attested deployment**.

Enrolled KMJ-elite source path:

`/srv/kmj-codebridge-projects/kmj-main-platform/work/qa/KMJ_CODEBRIDGE_OPERATOR_RECEIPT_BRIDGE_20261027.py`

Verify its SHA-256 before the owner runs it. To add new root-only operations, review full scripts and checksum, add only fixed named profiles and accepted status markers with tests. Do not enable free-form shell or elevated permissions.

Cross-chat continuity is separately supported via built-in `chat_continuity_save` / `multi_chat_sync` with stable lane `prod-release`. New chats should read that lane **before** asking the owner to repeat results.

## Current limitations

- Operator actions cannot wake a closed chat. On the next user message, the assistant can inspect receipts directly from CodeBridge.
- The initial helper only verifies private gateway port/service in read-only mode, not authenticated application route or production readiness.
- CodeBridge read access to a new receipts directory must be confirmed on device after the owner runs the profile.
- Approved execution profiles and host permissions remain unchanged, without bypass.