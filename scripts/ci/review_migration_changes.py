#!/usr/bin/env python3
"""Fail-closed advisory risk review for added Laravel migrations in a Git PR.

This is not a SQL parser, Bytebase replacement, or production migration runner.
It never connects to any database or prints SQL/customer data.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = "apps/platform/database/migrations/"
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
UP = re.compile(r"\bfunction\s+up\s*\(\s*\)\s*(?::\s*(?:void|mixed))?\s*\{")
RULES = (
    ("SCHEMA_DROP", re.compile(r"\bSchema\s*::\s*drop(?:IfExists)?\s*\(", re.I)),
    ("SCHEMA_RENAME", re.compile(r"\bSchema\s*::\s*rename\s*\(", re.I)),
    ("COLUMN_OR_INDEX_DROP", re.compile(r"->\s*drop(?:Column|Foreign|Index|Unique|Primary|ConstrainedForeignId)\s*\(", re.I)),
    ("COLUMN_RENAME_OR_CHANGE", re.compile(r"->\s*(?:renameColumn|change)\s*\(", re.I)),
    ("RAW_DATABASE_STATEMENT", re.compile(r"\bDB\s*::\s*(?:statement|unprepared|affectingStatement|update|delete|insert)\s*\(", re.I)),
    ("UNSAFE_DDL_LITERAL", re.compile(r"\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA|COLUMN)|TRUNCATE\s+(?:TABLE|ONLY)|ALTER\s+TABLE|CREATE\s+EXTENSION|GRANT\s+|REVOKE\s+)\b", re.I)),
    ("DISABLE_FK_GUARD", re.compile(r"\bSchema\s*::\s*disableForeignKeyConstraints\s*\(", re.I)),
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.DEVNULL).decode("utf-8", "strict")


def mask_comments(source: str) -> str:
    """Strip PHP comments without losing source positions or string literals."""
    out = list(source)
    i = 0
    state = "code"
    while i < len(source):
        c = source[i]
        pair = source[i : i + 2]
        if state == "code":
            if c in "'\"":
                state = c
            elif pair == "//" or c == "#":
                state = "line"
                out[i] = " "
                if pair == "//":
                    out[i + 1] = " "
                    i += 1
            elif pair == "/*":
                state = "block"
                out[i] = out[i + 1] = " "
                i += 1
        elif state in ("'", '"'):
            if c == "\\":
                i += 1
            elif c == state:
                state = "code"
        elif state == "line":
            if c == "\n":
                state = "code"
            else:
                out[i] = " "
        elif state == "block":
            if pair == "*/":
                out[i] = out[i + 1] = " "
                i += 1
                state = "code"
            elif c != "\n":
                out[i] = " "
        i += 1
    if state == "block":
        raise ValueError("UNCLOSED_COMMENT")
    return "".join(out)


def up_body(source: str) -> tuple[str, int]:
    stripped = mask_comments(source)
    matches = list(UP.finditer(stripped))
    if len(matches) != 1:
        raise ValueError("UP_METHOD_NOT_UNAMBIGUOUS")
    start = matches[0].end()
    depth = 1
    state = "code"
    i = start
    while i < len(stripped):
        c = stripped[i]
        if state == "code":
            if c in "'\"":
                state = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return stripped[start:i], stripped[:start].count("\n") + 1
        elif c == "\\":
            i += 1
        elif c == state:
            state = "code"
        i += 1
    raise ValueError("UP_METHOD_UNTERMINATED")


def audit_php(source: str) -> list[tuple[str, int]]:
    body, first_line = up_body(source)
    found = []
    for code, expression in RULES:
        for m in expression.finditer(body):
            found.append((code, first_line + body[:m.start()].count("\n")))
    return sorted(set(found), key=lambda item: (item[1], item[0]))


def changed_migrations(base: str, head: str) -> list[tuple[str, str]]:
    for sha in (base, head):
        if not COMMIT.fullmatch(sha):
            raise ValueError("INVALID_COMMIT_SHA")
        git("cat-file", "-e", f"{sha}^{{commit}}")
    fork = git("merge-base", base, head).strip()
    names = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff", "--name-status", "--no-renames", "-z", fork, head, "--", MIGRATIONS],
        stderr=subprocess.DEVNULL,
    ).decode("utf-8", "strict").split("\0")
    if names[-1] != "":
        raise ValueError("INVALID_GIT_DIFF")
    entries = names[:-1]
    if len(entries) % 2:
        raise ValueError("INVALID_GIT_DIFF")
    return list(zip(entries[::2], entries[1::2]))


def review(base: str, head: str) -> int:
    changes = changed_migrations(base, head)
    failures = 0
    added = 0
    for change, name in changes:
        if not name.startswith(MIGRATIONS) or not name.endswith(".php"):
            continue
        if change != "A":
            print(f"BLOCKED: MIGRATION_IMMUTABILITY {name} status={change}")
            failures += 1
            continue
        added += 1
        full = ROOT / name
        if full.is_symlink() or not full.is_file() or full.stat().st_size > 512_000:
            print(f"BLOCKED: UNREADABLE_MIGRATION {name}")
            failures += 1
            continue
        try:
            findings = audit_php(full.read_text(encoding="utf-8", errors="strict"))
        except (ValueError, UnicodeError):
            print(f"BLOCKED: UNINSPECTABLE_UP_METHOD {name}")
            failures += 1
            continue
        if not findings:
            print(f"PASS: REVIEWED_STATIC_PATTERNS {name}")
        for code, line in findings:
            print(f"BLOCKED: {code} {name}:{line} (requires separate authorized DB review)")
            failures += 1
    print(f"KMJ_MIGRATION_CHANGE_REVIEW={'PASS' if not failures else 'FAIL'} added={added} findings={failures}")
    print("SCOPE=STATIC_SOURCE_ONLY SQL_PARSER=NO DB_CONNECTED=NO PRODUCTION_WRITES=NO")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, help="exact base commit SHA")
    p.add_argument("--head", required=True, help="exact PR head commit SHA")
    args = p.parse_args()
    try:
        return review(args.base, args.head)
    except (ValueError, subprocess.CalledProcessError, OSError) as error:
        print(f"KMJ_MIGRATION_CHANGE_REVIEW=BLOCKED_PREFLIGHT reason={type(error).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
