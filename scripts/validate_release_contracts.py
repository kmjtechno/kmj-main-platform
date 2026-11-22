#!/usr/bin/env python3
"""Deny-by-default validator for KMJ release contracts (release/contracts/*.release.contract.json).

A contract names gates and probes. It never carries commands, paths, URLs, environment or secrets, never
selects a target SHA and never relaxes the owner approval. Any unknown key, odd character or duplicate JSON
key is an error. Exit code 0 only when every contract is valid.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "release" / "contracts"
MAX_BYTES = 8192
KINDS = {"laravel-elite", "node-service", "windows-installer", "cmake-qt", "static-site"}
DATA_RISK = {"none", "migrations", "destructive"}
SIGNING = {"none", "owner-signed-manifest", "code-signing-cert"}
SLUG = re.compile(r"[a-z][a-z0-9-]{1,40}\Z")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,40}(:[a-z0-9-]{1,40})?\Z")
CHECK = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ()+._/,:-]{0,119}\Z")
REPO = re.compile(r"kmjtechno/[a-z0-9][a-z0-9._-]{1,60}\Z")
TOP = {
    "schema_version", "project", "kind", "repository", "default_branch", "required_checks",
    "stage", "smoke", "health", "rollback", "data_risk", "approval", "signing",
}
NESTED = {"stage": "gate", "smoke": "probe", "health": "probe", "rollback": "strategy"}


def strict_load(data: bytes) -> dict:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate key {key!r}")
            out[key] = value
        return out

    def reject(name):
        raise ValueError(f"non-finite number {name}")

    if len(data) > MAX_BYTES:
        raise ValueError("file too large")
    obj = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject)
    if not isinstance(obj, dict):
        raise ValueError("top level must be an object")
    return obj


def validate(obj: dict, filename: str) -> list[str]:
    errors: list[str] = []
    unknown = set(obj) - TOP
    missing = TOP - set(obj)
    if unknown:
        errors.append(f"unknown keys: {sorted(unknown)}")
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    if errors:
        return errors
    if obj["schema_version"] != 1 or isinstance(obj["schema_version"], bool):
        errors.append("schema_version must be 1")
    project = obj["project"]
    if not isinstance(project, str) or not SLUG.fullmatch(project):
        errors.append("project must be a lowercase slug")
    elif filename != f"{project}.release.contract.json":
        errors.append("filename must be <project>.release.contract.json")
    if obj["kind"] not in KINDS:
        errors.append("kind not allowed")
    if not isinstance(obj["repository"], str) or not REPO.fullmatch(obj["repository"]):
        errors.append("repository must be kmjtechno/<name>")
    if obj["default_branch"] != "main":
        errors.append("default_branch must be main")
    checks = obj["required_checks"]
    if (not isinstance(checks, list) or not 1 <= len(checks) <= 20
            or any(not isinstance(c, str) or not CHECK.fullmatch(c) for c in checks)
            or len(set(checks)) != len(checks)):
        errors.append("required_checks must be 1-20 unique plain check names")
    for key, inner in NESTED.items():
        value = obj[key]
        if (not isinstance(value, dict) or set(value) != {inner}
                or not isinstance(value[inner], str) or not NAME.fullmatch(value[inner])):
            errors.append(f"{key} must be {{{inner!r}: <named gate>}} (a name, never a command)")
    if obj["data_risk"] not in DATA_RISK:
        errors.append("data_risk not allowed")
    if obj["approval"] != "owner-passkey":
        errors.append("approval must be owner-passkey")
    if obj["signing"] not in SIGNING:
        errors.append("signing not allowed")
    if obj["data_risk"] == "destructive" and obj["signing"] == "none":
        errors.append("destructive releases must declare a signing or approval artifact")
    return errors


def main(directory: Path = DIR) -> int:
    files = sorted(directory.glob("*.release.contract.json"))
    if not files:
        print("RELEASE_CONTRACTS=BLOCKED_NONE_FOUND")
        return 1
    failed = 0
    projects: set[str] = set()
    for path in files:
        try:
            obj = strict_load(path.read_bytes())
            errors = validate(obj, path.name)
            if not errors and obj["project"] in projects:
                errors = ["duplicate project"]
            projects.add(str(obj.get("project")))
        except (ValueError, UnicodeError) as exc:
            errors = [str(exc)]
        for error in errors:
            print(f"{path.name}: {error}")
        failed += bool(errors)
    print(f"RELEASE_CONTRACTS={'FAIL' if failed else 'PASS'} contracts={len(files)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
