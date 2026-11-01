#!/usr/bin/env python3
"""A2 offline decision planner for the legacy offsite SSH exit 255.

Pure and offline: reads sanitized key=value receipts (A2 inspect, A2b compare,
A2c trace and an optional restore witness) from files named on the command line
and prints ONE decision plus the owner gates that must be met. It opens no
network connection, runs no subprocess, writes nothing, reads no key, config or
journal, and can never authorize a change: APPLY_ALLOWED is always NO. The
output is a plan for a reviewed, owner-run operator step, not an action.

Decisions (deny by default):
  BLOCKED_EVIDENCE            receipts missing, duplicated, unknown schema or unsafe values
  NOT_AUTH_FAILURE            exit 255 is not an exact-invocation publickey denial; use the other class
  INVESTIGATE_INCONSISTENT    receipts contradict each other; no plan is produced
  REPOINT_IDENTITY_REVIEW     legacy offered key is a single unauthorized candidate: plan a reviewed
                              drop-in using the already-authorized pinned identity (no new key, no rotation)
  RETIRE_LEGACY_REVIEW        legacy identity ambiguous/unproven: plan retiring the legacy unit in favour of
                              the reviewed pinned SFTP push (never "restart and hope")
Both review decisions additionally require a fresh independent restore witness; without it the
decision is downgraded to WAIT_FOR_RESTORE_WITNESS.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_BYTES = 16384
LINE = re.compile(r"([a-z][a-z0-9_]{0,63})=([A-Za-z0-9_.:,+/=-]{1,400})\Z")
SCHEMAS = {"kmj.a2.ssh255.readonly.v1", "kmj.a2.unit-identity.readonly.v1"}
FORBIDDEN_VALUE = re.compile(r"(^/|\.\./|BEGIN [A-Z ]*KEY|@)")
GATES = (
    "fresh encrypted PostgreSQL + ALL customer uploads backup with witnessed source SHA",
    "remote no-clobber upload with 0600 readback of that exact ciphertext",
    "independent disposable restore PASS (bwrap, pinned scripts)",
    "owner/root operator executes the reviewed step; legacy timer, keys and known_hosts unchanged until then",
    "post-change read-only A2 diagnostic shows no new 255 and no automatic retry loop",
)


def parse(text: str) -> dict[str, str] | None:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.endswith("READ_ONLY_COMPLETE"):
            continue
        match = LINE.fullmatch(line)
        if match is None or FORBIDDEN_VALUE.search(match.group(2)):
            return None
        key, value = match.groups()
        if key in values and values[key] != value:
            return None
        values[key] = value
    return values


def merge(documents: list[str]) -> dict[str, str] | None:
    merged: dict[str, str] = {}
    schemas = set()
    for text in documents:
        if len(text.encode()) > MAX_BYTES:
            return None
        values = parse(text)
        if values is None:
            return None
        if "schema" in values:
            schemas.add(values["schema"])
        for key, value in values.items():
            if key == "schema":
                continue
            if key in merged and merged[key] != value:
                return None
            merged[key] = value
    if schemas - SCHEMAS:
        return None
    merged["_schemas"] = ",".join(sorted(schemas))
    return merged


def plan(documents: list[str]) -> dict[str, str]:
    out = {"APPLY_ALLOWED": "NO", "MUTATIONS": "NONE"}
    r = merge(documents)
    if r is None or "kmj.a2.ssh255.readonly.v1" not in r["_schemas"].split(","):
        return {**out, "DECISION": "BLOCKED_EVIDENCE"}
    if (r.get("exit_255") != "YES" or r.get("journal_scope") != "EXACT_INVOCATION"
            or r.get("journal_failure_class") != "SSH_AUTH_KEY_REJECTED"
            or r.get("journal_auth_subclass") != "PUBLICKEY_AUTH_DENIED"):
        return {**out, "DECISION": "NOT_AUTH_FAILURE"}
    if r.get("raw_values_emitted", "NO") != "NO" or r.get("mutations", "NONE") != "NONE":
        return {**out, "DECISION": "BLOCKED_EVIDENCE"}
    reads_cfg = r.get("executable_reads_sftp_config")
    if reads_cfg is None:
        return {**out, "DECISION": "BLOCKED_EVIDENCE", "NEEDS": "A2b unit identity receipt"}
    # A legacy unit that really uses the authorized pinned identity cannot be denied for it.
    if reads_cfg == "YES" and r.get("authorized_fingerprint_match") == "YES":
        return {**out, "DECISION": "INVESTIGATE_INCONSISTENT"}
    single = (r.get("effective_identity") == "SINGLE_CANDIDATE_UNPROVEN"
              and r.get("authorized_overlap") == "NO")
    decision = "REPOINT_IDENTITY_REVIEW" if single else "RETIRE_LEGACY_REVIEW"
    witness = (r.get("restore_verified") == "PASS" and r.get("restore_scope") == "DB_AND_ALL_UPLOADS"
               and re.fullmatch(r"[a-f0-9]{64}", r.get("source_local_sha256", "")) is not None)
    if not witness:
        out["PLANNED_AFTER_WITNESS"] = decision
        decision = "WAIT_FOR_RESTORE_WITNESS"
    out["DECISION"] = decision
    out["OWNER_GATES"] = str(len(GATES))
    for index, gate in enumerate(GATES, 1):
        out[f"GATE_{index}"] = gate.replace(" ", "_").replace("+", "and")
    out["IDENTITY_SOURCE"] = "UNPROVEN"
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2 or len(argv) > 5:
        print("PLAN=BLOCKED_USAGE")
        return 2
    documents = []
    for name in argv[1:]:
        path = Path(name)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            print("PLAN=BLOCKED_INPUT_FILE")
            return 2
        documents.append(path.read_text(encoding="ascii", errors="strict"))
    for key, value in plan(documents).items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
