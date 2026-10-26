#!/usr/bin/env python3
"""Fail-closed source-secret and optional production environment preflight.

Never prints credential values. Uses only Python's standard library.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess

MAX_TEXT_BYTES = 5 * 1024 * 1024
TEXT_EXTENSIONS = frozenset({
    ".php", ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yml",
    ".yaml", ".sh", ".md", ".txt", ".xml", ".toml", ".ps1", ".cmd",
})
SKIP_BASENAMES = frozenset({"package-lock.json", "composer.lock"})
CREDENTIAL_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("OpenAI/Anthropic key", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{20,}\b")),
)


def is_private_path(relative: str) -> bool:
    name = Path(relative).name.lower()
    if name.startswith(".env") and not name.endswith(".example"):
        return True
    if name in {"id_rsa", "id_ed25519", "agent.json", "gateway.json"}:
        return True
    return name.endswith((".pem", ".p12", ".pfx", ".key"))


def scan_source_text(text: str, label: str) -> list[str]:
    findings: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in CREDENTIAL_PATTERNS:
            if pattern.search(line):
                findings.append(f"{label}:{number}: {kind}")
    return findings


def scan_tracked_tree(root: Path) -> tuple[list[str], int]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    )
    paths = [p.decode("utf-8") for p in result.stdout.split(b"\0") if p]
    findings: list[str] = []
    scanned = 0
    for relative in paths:
        path = root / relative
        if is_private_path(relative):
            findings.append(f"{relative}: tracked private configuration")
            continue
        if path.is_symlink():
            findings.append(f"{relative}: tracked symlink requires separate review")
            continue
        if path.name in SKIP_BASENAMES or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if not path.is_file():
            findings.append(f"{relative}: tracked file missing")
            continue
        if path.stat().st_size > MAX_TEXT_BYTES:
            findings.append(f"{relative}: oversized text cannot be security-scanned")
            continue
        raw = path.read_bytes()
        if b"\x00" in raw:
            findings.append(f"{relative}: unexpected binary content in text file")
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"{relative}: undecodable text")
            continue
        scanned += 1
        findings.extend(scan_source_text(content, relative))
    return findings, scanned


def validate_production_env(text: str) -> list[str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip(chr(39))
    required = {
        "APP_ENV": lambda value: value == "production",
        "APP_DEBUG": lambda value: value.lower() in {"false", "0"},
        "APP_URL": lambda value: value.startswith("https://")
        and "@" not in value.split("/", 3)[2],
        "SESSION_SECURE_COOKIE": lambda value: value.lower() in {"true", "1"},
    }
    return [
        f"{name}: missing or insecure for production"
        for name, checker in required.items()
        if not checker(values.get(name, ""))
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", action="store_true")
    parser.add_argument("--production-env", type=Path)
    args = parser.parse_args()
    if not args.repository and args.production_env is None:
        parser.error("select --repository or --production-env")
    findings: list[str] = []
    if args.repository:
        tree_findings, count = scan_tracked_tree(Path.cwd())
        findings.extend(tree_findings)
        print(f"TRACKED_TEXT_FILES_SCANNED={count}")
    if args.production_env is not None:
        try:
            findings.extend(validate_production_env(args.production_env.read_text()))
        except (OSError, UnicodeError):
            findings.append("production environment: missing or unreadable")
    for finding in findings:
        print(f"SECURITY_GATE_FAIL={finding}")
    if findings:
        print("SECURE_AI_RELEASE_GATE=FAIL")
        return 1
    print("SECURE_AI_RELEASE_GATE=PASS_STATIC_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
