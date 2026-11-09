"""Fixed 09e8 candidate-only V6 CLOSED receipt validation -- source-only, NO host I/O.

The protected scanner archives its newline-delimited journal as
<sha256(candidate app path)[:12]>.journal.done-<timestamp>. This module
validates that a completed receipt for the exact candidate/plan was actually
consistent with the scanner's reviewed schema and phase order. It NEVER
substitutes for root ownership checks, fd-anchored snapshot attestation,
immutable flags, the admission guard, or a live-pointer readback.

No filesystem access, imports of production code, application bootstrap,
systemctl, git, subprocess or operational CLI are provided here.
"""
from __future__ import annotations

import hashlib
import json
import re

CANDIDATE_SHA = "09e8a224cd37445c42588a073a6b52d207475a09"
CANDIDATE_APP = "/home/kmjprod/releases/platform-09e8a224cd37/apps/platform"
LIVE_RELEASE = "platform-bce4100d005e"
SHARED = "/home/kmjprod/shared/storage"
V6_SCANNER_SHA256 = "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba"

KEY = hashlib.sha256(CANDIDATE_APP.encode("utf-8")).hexdigest()[:12]
HEX16 = re.compile(r"[0-9a-f]{16}\Z")
LINK_NAME = re.compile(r"\.kmj-storage-link-[0-9a-f]{16}\Z")
KEPT_NAME = re.compile(r"storage\.pre-shared-[0-9]{8}T[0-9]{6}Z\Z")
DONE_NAME = re.compile(re.escape(KEY) + r"\.journal\.done-[0-9]+\Z")
EXPECTED_FIRST = ("begin", "live_frozen", "both_frozen",
                  "link_created", "exchanged")
ALLOWED_PHASES = frozenset((*EXPECTED_FIRST, "preserved", "verified", "complete"))
ALLOWED_FIELDS = {
    "begin": frozenset(("phase", "t", "plan", "link", "kept")),
    "both_frozen": frozenset(("phase", "t", "shared_plan")),
}
BASIC_FIELDS = frozenset(("phase", "t"))
MAX_BYTES = 65536
MAX_RECORDS = 200


class ReceiptRejected(ValueError):
    pass


def check(ok: bool, reason: str) -> None:
    if not ok:
        raise ReceiptRejected(reason)


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    record = {}
    for key, value in pairs:
        check(key not in record, "DUPLICATE_KEY")
        record[key] = value
    return record


def decode_closed_journal(raw: bytes) -> list[dict]:
    """Reject torn final lines, duplicates, non-objects and excessive input."""
    check(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES
          and raw.endswith(b"\n"), "JOURNAL_INCOMPLETE")
    records = []
    lines = raw[:-1].split(b"\n")
    check(0 < len(lines) <= MAX_RECORDS, "JOURNAL_ROWS")
    for line in lines:
        check(bool(line), "BLANK_JOURNAL_ROW")
        try:
            item = json.loads(line.decode("utf-8", "strict"),
                              object_pairs_hook=no_duplicate_keys,
                              parse_constant=lambda _: (_ for _ in ()).throw(
                                  ReceiptRejected("NONFINITE_JSON")))
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise ReceiptRejected("MALFORMED_JOURNAL") from exc
        check(type(item) is dict, "NOT_OBJECT")
        records.append(item)
    return records


def validate_candidate_receipt(
    raw: bytes, *, closed_filename: str,
    snapshot_name: str, plan_id: str,
) -> dict[str, str]:
    """Pure structural receipt proof: cannot attest on-disk files or drain.

    The caller still MUST independently attest:
      * root-owned 0700 state directory, stable inode and no active journal;
      * exactly one closed receipt for this exact app in that directory;
      * root-owned complete protected receipt bytes (not a symlink);
      * this candidate SHA & clean source via root-protected attestor;
      * shared link literal target + fd inode equality after v6 switch;
      * exactly one preserved candidate snapshot still immutable;
      * saved plan of preserved snapshot and all shared inodes fully thawed;
      * LIVE link and release pointer unchanged before AND after the scan;
      * process exclusion guard still owned and all writers still drained.
    """
    check(type(closed_filename) is str and DONE_NAME.fullmatch(closed_filename)
          is not None, "WRONG_CANDIDATE_CLOSED_RECEIPT")
    check(type(snapshot_name) is str and KEPT_NAME.fullmatch(snapshot_name)
          is not None, "SNAPSHOT_NAME_INVALID")
    check(type(plan_id) is str and HEX16.fullmatch(plan_id) is not None,
          "PLAN_ID_INVALID")
    records = decode_closed_journal(raw)
    phases = tuple(record.get("phase") for record in records)
    check(len(phases) >= 7 and phases[:5] == EXPECTED_FIRST,
          "V6_PHASES_MISSING_OR_REORDERED")
    suffix = list(phases[5:])
    if suffix[:1] == ["preserved"]:
        suffix.pop(0)
    check(suffix and suffix[0] == "verified" and
          len(suffix) >= 2 and all(p == "complete" for p in suffix[1:]),
          "V6_NOT_COMPLETED")
    prev_time = 0
    for idx, record in enumerate(records):
        phase = record.get("phase")
        check(type(phase) is str and phase in ALLOWED_PHASES, "UNSUPPORTED_PHASE")
        check(set(record) == ALLOWED_FIELDS.get(phase, BASIC_FIELDS),
              "JOURNAL_FIELDS_INVALID")
        t = record["t"]
        check(type(t) is int and 0 < t <= 99999999999 and t >= prev_time,
              "TIMESTAMP_UNTRUSTED")
        prev_time = t
        if phase == "begin":
            check(record["plan"] == plan_id and
                  type(record["plan"]) is str, "PLAN_BINDING_MISMATCH")
            check(record["kept"] == snapshot_name and
                  type(record["kept"]) is str, "SNAPSHOT_BINDING_MISMATCH")
            check(type(record["link"]) is str and
                  LINK_NAME.fullmatch(record["link"]) is not None,
                  "LINK_NAME_INVALID")
        elif phase == "both_frozen":
            check(type(record["shared_plan"]) is str and
                  HEX16.fullmatch(record["shared_plan"]) is not None,
                  "SHARED_PLAN_INVALID")
    check(phases.count("begin") == phases.count("verified") == 1
          and phases.count("both_frozen") == 1, "AMBIGUOUS_PHASES")
    # Plan IDs and filenames only, never sensitive customer upload paths.
    return {
        "CANDIDATE_SHA": CANDIDATE_SHA,
        "EXPECTED_LIVE_RELEASE": LIVE_RELEASE,
        "CANDIDATE_RECEIPT_PHASES": "VALID_COMPLETE",
        "CANDIDATE_RECEIPT_PLAN_MATCH": "YES",
        "CANDIDATE_RECEIPT_SNAPSHOT_MATCH": "YES",
        "SOURCE_ONLY_VALIDATION": "PASS",
        "ROOT_FS_ATTESTATION": "NOT_PERFORMED",
        "WRITER_EXCLUSION": "NOT_ATTESTED",
        "STORAGE_APPLY_ALLOWED": "NO",
        "PRODUCTION_ACTIVATION_ALLOWED": "NO",
    }


if __name__ == "__main__":
    raise SystemExit("SOURCE_ONLY_NO_HOST_ENTRYPOINT")
