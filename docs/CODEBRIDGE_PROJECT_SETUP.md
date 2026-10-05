# KMJ Main Platform — CodeBridge Project Setup

This file is intentionally secret-free. CodeBridge credentials and the real `agent.json` belong outside this Git repository.

## Intended project

- Repository: `kmjtechno/kmj-main-platform`
- Preferred CodeBridge project id: `kmj-main-platform`
- Production path currently used by platform probes: `/home/kmjprod/current`
- Safe default: read-only until the project identity is verified.
- Enable `writable: true` only for the explicitly authorized development checkout.
- Do not create a second project when a free/community agent is already using its one-project allowance; first verify whether the existing authorized project is this repository.

## Verification before enabling writes

Use CodeBridge read tools and confirm all of these:
- `README.md` identifies KMJ Main Platform.
- `apps/platform/composer.json` has package name `kmjtechno/kmj-main-platform`.
- `apps/platform/package.json` has package name `@kmjtechno/main-platform`.
- Git status is understood and unrelated dirty work will be preserved.

If any identity check fails, do not write.

## Recommended administrator-configured gates

Add these entries to the private CodeBridge agent project's `gates` object. Keep the private agent config outside the repository.

```json
{
  "fast": {
    "command": "/bin/bash",
    "args": ["scripts/codebridge-quality-gate.sh", "fast"],
    "timeoutMs": 120000
  },
  "platform": {
    "command": "/bin/bash",
    "args": ["scripts/codebridge-quality-gate.sh", "platform"],
    "timeoutMs": 300000
  },
  "full": {
    "command": "/bin/bash",
    "args": ["scripts/codebridge-quality-gate.sh", "full"],
    "timeoutMs": 300000
  }
}
```

CodeBridge executes configured gates with the project root as the working directory. These gates do not install dependencies, deploy, change DNS, rotate secrets, run destructive database operations, or mutate billing/signing-key state.

## Suggested project object

Use this only as a shape reference when updating the private agent configuration:

```json
{
  "id": "kmj-main-platform",
  "root": "/absolute/path/to/the/authorized/kmj-main-platform/checkout",
  "writable": true,
  "gates": {
    "fast": {
      "command": "/bin/bash",
      "args": ["scripts/codebridge-quality-gate.sh", "fast"],
      "timeoutMs": 120000
    },
    "platform": {
      "command": "/bin/bash",
      "args": ["scripts/codebridge-quality-gate.sh", "platform"],
      "timeoutMs": 300000
    },
    "full": {
      "command": "/bin/bash",
      "args": ["scripts/codebridge-quality-gate.sh", "full"],
      "timeoutMs": 300000
    }
  }
}
```

Do not paste the agent token, gateway credential, OAuth token or license credential into this file.

## Claude startup sequence

After the private CodeBridge config is active:
1. `connection_doctor` / `inspect_project`
2. `project_snapshot`
3. read `CLAUDE.md`
4. inspect the current task and relevant roadmap/gate files
5. use guarded edits
6. run `fast`
7. run `platform` or `full` only when warranted
8. inspect diff and test evidence
9. commit only a scoped, verified slice
