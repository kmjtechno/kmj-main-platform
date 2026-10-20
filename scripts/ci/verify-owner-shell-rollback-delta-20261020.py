#!/usr/bin/env python3
"""Exact-source rollback delta fence for 2026-10-20 owner-shell candidate.

READ ONLY. Proves only the Git source delta does not touch application
migrations, payment/licensing backend or runtime configuration. Does NOT
prove live data restore, rollback activation or offsite backup readiness.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OLD = "8070dad72c551e5e13d1a78b0d4e6933c2d2ae9b"
NEW = "ad7655615b4da4f0c87a42e4036f1de7d9dd1812"

# Exact materialized delta recorded by GitHub between the immutable releases.
EXPECTED = {
    ".github/workflows/immutable-production-candidate-contract.yml": "A",
    ".github/workflows/local-production-recovery-contract.yml": "A",
    "apps/platform/resources/css/owner-module-shell.css": "A",
    "apps/platform/resources/js/app.tsx": "M",
    "apps/platform/resources/js/layouts/owner-module-shell.tsx": "A",
    "apps/platform/scripts/browser-preview-verify.mjs": "M",
    "apps/platform/scripts/check-command-os-visual-lock.test.mjs": "M",
    "apps/platform/scripts/check-visual-qa-coverage.test.mjs": "M",
    "apps/platform/visual/entry.tsx": "M",
    "scripts/operations/build-main-platform-candidate-kmj-elite.sh": "A",
    "scripts/operations/prepare-main-platform-local-recovery-kmj-elite.sh": "A",
    "scripts/test_main_platform_candidate_build_contract.py": "A",
    "scripts/test_main_platform_local_recovery_contract.py": "A",
}


def validate_delta(entries: dict[str, str]) -> None:
    # Check sensitive paths independently for readable fail-closed diagnostics.
    forbidden_prefixes = (
        "apps/platform/database/migrations/",
        "apps/platform/app/Http/Controllers/Payments/",
        "apps/platform/app/Services/Payments/",
        "apps/platform/app/Services/Licensing/",
        "apps/platform/config/",
        "apps/platform/routes/",
    )
    forbidden_names = {
        "apps/platform/composer.lock",
        "apps/platform/package-lock.json",
        "apps/platform/.env",
    }
    for path in entries:
        if path in forbidden_names or path.startswith(forbidden_prefixes):
            raise AssertionError("PROTECTED_RUNTIME_SOURCE_CHANGED")
    if entries != EXPECTED:
        added = sorted(set(entries) - set(EXPECTED))
        missing = sorted(set(EXPECTED) - set(entries))
        changed_status = sorted(
            p for p in set(entries) & set(EXPECTED)
            if entries[p] != EXPECTED[p]
        )
        raise AssertionError(
            "EXACT_RELEASE_SOURCE_DELTA_MISMATCH "
            f"added={added} missing={missing} status={changed_status}"
        )


def git(*args: str) -> bytes:
    root = Path(__file__).resolve().parents[2]
    return subprocess.check_output(
        ["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", *args],
        stderr=subprocess.DEVNULL,
        timeout=30,
    )


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("UNEXPECTED_CLI_ARGUMENTS")
    for sha in (OLD, NEW):
        git("cat-file", "-e", sha + "^{commit}")
    git("merge-base", "--is-ancestor", OLD, NEW)
    raw = git("diff", "--no-ext-diff", "--name-status", "-z", OLD, NEW)
    fields = raw.split(b"\0")
    if fields[-1:] != [b""]:
        raise AssertionError("INVALID_GIT_DELTA_END")
    fields.pop()
    if len(fields) % 2:
        raise AssertionError("INVALID_GIT_DELTA_FORMAT")
    entries: dict[str, str] = {}
    for i in range(0, len(fields), 2):
        status = fields[i].decode("ascii", errors="strict")
        path = fields[i + 1].decode("utf-8", errors="strict")
        if not status in ("A", "M") or path in entries:
            raise AssertionError("UNEXPECTED_GIT_DELTA_RECORD")
        entries[path] = status
    validate_delta(entries)
    print(f"OLD_PRODUCTION_SHA={OLD}")
    print(f"STAGED_OWNER_SHELL_SHA={NEW}")
    print(f"EXACT_SOURCE_DELTA_FILES={len(entries)}")
    print("DATABASE_MIGRATION_DELTA=NONE")
    print("PAYMENTS_LICENSING_BACKEND_DELTA=NONE")
    print("SOURCE_ROLLBACK_DELTA_GATE=PASS")
    print("REAL_PRODUCTION_ROLLBACK_DRILL=NOT_VERIFIED")
    print("INDEPENDENT_OFFSITE_RESTORE=NOT_VERIFIED")
    print("PRODUCTION_SWITCH=NOT_ATTEMPTED")


if __name__ == "__main__":
    main()
