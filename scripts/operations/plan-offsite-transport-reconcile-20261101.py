#!/usr/bin/env python3
"""A2 offline decision planner for the legacy offsite SSH exit 255.

Only accepts fixed, sanitized, schema-bound A2/A2b/A2c diagnostics.
Diagnostic restore_verified=NO is an observation, not a global release state.
A separately typed and independently authenticated restore witness is NOT
implemented here. Arbitrary text claiming PASS can never clear a release gate.
No shell, SSH, key, systemd, network, writes, or production authority.
APPLY_ALLOWED=NO and MUTATIONS=NONE for every path.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_BYTES = 16384
LINE = re.compile(r"([A-Za-z][A-Za-z0-9_]{0,63})=([^\r\n]{1,400})\Z")
SAFE_VALUE = re.compile(r"[A-Za-z0-9_.:,+/=-]{1,400}\Z")
TRACE_CANDIDATE = re.compile(
    r"id=[a-f0-9]{12} role=PRIVATE_KEY kind=FILE keys=- "
    r"fps=SHA256:[A-Za-z0-9+/]{43}\Z"
)
A2 = "kmj.a2.ssh255.readonly.v1"
A2B = "kmj.a2.unit-identity.readonly.v1"
A2C = "kmj.a2c.effective-identity.readonly.v1"
ALLOWED = {
    A2: frozenset("""schema unit unit_load exit_255 systemd_user execstart_reference
        execstart_hash_attested journal_scope journal_failure_class
        journal_auth_subclass sftp_config sftp_identity hostkey_pin
        backup_created restore_verified production_changed
        raw_values_emitted A2_DIAGNOSTIC""".split()),
    A2B: frozenset("""schema unit unit_loaded dropins_present single_execstart
        executable_protected executable_sha256 executable_reads_sftp_config
        executable_embeds_other_identity config_identity_present
        config_identity_protected config_identity_fingerprint
        authorized_fingerprint_match service_identity_source
        local_reference_hint repair_precondition_met
        remote_authorization_witnessed backup_created restore_verified
        mutations raw_values_emitted A2B_COMPARE""".split()),
    A2C: frozenset("""schema unit unit_user dropins_present executable
        tools_referenced referenced_paths_scanned unit_home_resolved
        candidate_files candidate_0 candidate_fingerprints
        authorized_overlap effective_identity remote_auth_witnessed
        repair_allowed backup_created restore_verified mutations
        raw_values_emitted A2C_TRACE""".split()),
}
REQUIRED = {
    A2: {"unit", "exit_255", "journal_scope", "journal_failure_class",
         "journal_auth_subclass", "restore_verified", "raw_values_emitted",
         "A2_DIAGNOSTIC"},
    A2B: {"unit", "executable_reads_sftp_config",
          "authorized_fingerprint_match", "service_identity_source",
          "repair_precondition_met", "remote_authorization_witnessed",
          "restore_verified", "mutations", "raw_values_emitted", "A2B_COMPARE"},
    A2C: {"unit", "effective_identity", "authorized_overlap",
          "remote_auth_witnessed", "restore_verified", "mutations",
          "raw_values_emitted", "A2C_TRACE"},
}
UNIT = "kmj-elite-offsite-backup.service"

GATES = (
    "fresh encrypted PostgreSQL + ALL customer uploads backup with witnessed source SHA",
    "remote no-clobber upload with 0600 readback of that exact ciphertext",
    "independent disposable restore PASS (bwrap, pinned scripts)",
    "owner/root operator executes the reviewed step; legacy timer, keys and known_hosts unchanged until then",
    "post-change read-only A2 diagnostic shows no new 255 and no automatic retry loop",
)


def parse(text: str) -> dict[str, str] | None:
    if len(text.encode("utf-8")) > MAX_BYTES:
        return None
    values: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw:
            continue
        match = LINE.fullmatch(raw)
        if match is None:
            return None
        key, value = match.groups()
        if key in values:
            return None
        if key == "candidate_0":
            if not TRACE_CANDIDATE.fullmatch(value):
                return None
        elif not SAFE_VALUE.fullmatch(value) or value.startswith("/") or "../" in value:
            return None
        values[key] = value
    schema = values.get("schema")
    if schema not in ALLOWED or not REQUIRED[schema] <= values.keys():
        return None
    if values.keys() - ALLOWED[schema]:
        return None
    if values.get("unit") != UNIT or values.get("raw_values_emitted") != "NO":
        return None
    marker = {A2: "A2_DIAGNOSTIC", A2B: "A2B_COMPARE", A2C: "A2C_TRACE"}[schema]
    if values[marker] != "READ_ONLY_COMPLETE":
        return None
    if values.get("restore_verified") != "NO":
        return None
    if schema in (A2B, A2C) and values.get("mutations") != "NONE":
        return None
    if schema == A2B and (values["repair_precondition_met"] != "NO"
                         or values["remote_authorization_witnessed"] != "NO"
                         or values["executable_reads_sftp_config"] not in ("YES", "NO")
                         or values["authorized_fingerprint_match"] not in
                         ("YES", "NO", "UNKNOWN_NO_OWNER_ALLOWLIST")):
        return None
    if schema == A2C and values["remote_auth_witnessed"] != "NO":
        return None
    return values


def merge(documents: list[str]) -> dict[str, dict[str, str]] | None:
    """Keep diagnostic scopes separate; duplicate schemas and fake witnesses fail."""
    result: dict[str, dict[str, str]] = {}
    for raw in documents:
        values = parse(raw)
        if values is None or values["schema"] in result:
            return None
        result[values["schema"]] = values
    return result


def plan(documents: list[str]) -> dict[str, str]:
    out = {"APPLY_ALLOWED": "NO", "MUTATIONS": "NONE"}
    receipts = merge(documents)
    if receipts is None or A2 not in receipts or A2B not in receipts:
        return {**out, "DECISION": "BLOCKED_EVIDENCE"}
    a, b = receipts[A2], receipts[A2B]
    if (a.get("exit_255") != "YES"
            or a.get("journal_scope") != "EXACT_INVOCATION"
            or a.get("journal_failure_class") != "SSH_AUTH_KEY_REJECTED"
            or a.get("journal_auth_subclass") != "PUBLICKEY_AUTH_DENIED"):
        return {**out, "DECISION": "NOT_AUTH_FAILURE"}
    if (b["executable_reads_sftp_config"] == "YES"
            and b["authorized_fingerprint_match"] == "YES"):
        return {**out, "DECISION": "INVESTIGATE_INCONSISTENT"}

    # A key candidate is not evidence of the identity actually offered by SSH.
    # No receipt from this parser authenticates an independent Google restore.
    # In particular, a schema-less restore_verified=PASS is refused outright.
    # Future acceptance requires a separate, cryptographically bound witness
    # verifier that binds candidate, ciphertext SHA, source and restore scope.
    out["DECISION"] = "WAIT_FOR_RESTORE_WITNESS"
    out["PLANNED_AFTER_WITNESS"] = "RETIRE_LEGACY_REVIEW"
    out["RESTORE_PROVENANCE"] = "UNVERIFIED"
    out["IDENTITY_SOURCE"] = "UNPROVEN"
    out["OWNER_GATES"] = str(len(GATES))
    for index, gate in enumerate(GATES, 1):
        out[f"GATE_{index}"] = gate.replace(" ", "_").replace("+", "and")
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
