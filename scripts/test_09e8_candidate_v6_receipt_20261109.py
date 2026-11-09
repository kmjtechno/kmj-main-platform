#!/usr/bin/env python3
"""Untrusted real-v6-JSONL adversarial tests; isolated pure functions, no root."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

SOURCE = (Path(__file__).resolve().parent / "operations" /
          "09e8-candidate-only-cutover-review/receipt_validation.py")
SPEC = importlib.util.spec_from_file_location("candidate09e8receipt", SOURCE)
v = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v
SPEC.loader.exec_module(v)

STAMP = 1794227100
PLAN = "c651c450b3941f3a"
KEEP = "storage.pre-shared-20261109T095500Z"
LINK = ".kmj-storage-link-0123456789abcdef"
DONE = v.KEY + ".journal.done-1794227100"


def success_records():
    phases = ["begin", "live_frozen", "both_frozen", "link_created",
              "exchanged", "preserved", "verified", "complete"]
    result = []
    for i, phase in enumerate(phases):
        record = {"phase": phase, "t": STAMP + i}
        if phase == "begin":
            record.update(link=LINK, kept=KEEP, plan=PLAN)
        if phase == "both_frozen":
            record["shared_plan"] = "a123456789abcdef"
        result.append(record)
    return result


def serialize(records):
    return b"".join(json.dumps(row, separators=(",", ":")).encode() + b"\n"
                    for row in records)


def validate(records, **kw):
    args = {"closed_filename": DONE, "snapshot_name": KEEP, "plan_id": PLAN}
    args.update(kw)
    return v.validate_candidate_receipt(
        records if isinstance(records, bytes) else serialize(records), **args
    )


class ReceiptTests(unittest.TestCase):
    def test_fixed_candidate_identity(self):
        self.assertEqual(v.CANDIDATE_SHA, "09e8a224cd37445c42588a073a6b52d207475a09")
        self.assertEqual(v.CANDIDATE_APP,
                         "/home/kmjprod/releases/platform-09e8a224cd37/apps/platform")
        self.assertNotEqual(v.LIVE_RELEASE, "platform-574e443a2c75")

    def test_full_v6_order_and_nonmutating_contract(self):
        result = validate(success_records())
        self.assertEqual(result["CANDIDATE_RECEIPT_PLAN_MATCH"], "YES")
        self.assertEqual(result["CANDIDATE_RECEIPT_PHASES"], "VALID_COMPLETE")
        self.assertEqual(result["ROOT_FS_ATTESTATION"], "NOT_PERFORMED")
        self.assertEqual(result["STORAGE_APPLY_ALLOWED"], "NO")
        self.assertEqual(result["PRODUCTION_ACTIVATION_ALLOWED"], "NO")

    def test_valid_without_optional_preserved_phase(self):
        rows = [item for item in success_records() if item["phase"] != "preserved"]
        self.assertEqual(validate(rows)["SOURCE_ONLY_VALIDATION"], "PASS")

    def test_wrong_candidate_receipt_file(self):
        for bad in ("deadbeefdead.journal.done-100",
                    v.KEY + ".journal", "../../" + DONE,
                    DONE + ".bak", v.KEY + ".journal.done-0x10"):
            with self.subTest(name=bad), self.assertRaises(v.ReceiptRejected):
                validate(success_records(), closed_filename=bad)

    def test_tampered_snapshot_or_plan(self):
        for field, value in (("kept", "storage.pre-shared-20261109T000000Z"),
                             ("plan", "aaaaaaaaaaaaaaaa"),
                             ("link", ".kmj-storage-link-GGGGGGGGGGGGGGGG")):
            rows = success_records()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(v.ReceiptRejected):
                validate(rows)
        with self.assertRaises(v.ReceiptRejected):
            validate(success_records(), plan_id="b" * 16)
        with self.assertRaises(v.ReceiptRejected):
            validate(success_records(), snapshot_name="../../" + KEEP)

    def test_absent_verified_or_complete_is_not_success(self):
        for phase in ("verified", "complete", "exchanged", "both_frozen"):
            rows = [r for r in success_records() if r["phase"] != phase]
            with self.subTest(phase=phase), self.assertRaises(v.ReceiptRejected):
                validate(rows)

    def test_wrong_sequence_or_rollback_refuses(self):
        rows = success_records()
        rows[2], rows[3] = rows[3], rows[2]
        with self.assertRaises(v.ReceiptRejected):
            validate(rows)
        rows = success_records()
        rows[-1]["phase"] = "rollback_exchanged"
        with self.assertRaises(v.ReceiptRejected):
            validate(rows)

    def test_duplicate_json_keys_refused(self):
        rows = serialize(success_records())
        rows = rows.replace(b'"phase":"begin"', b'"phase":"begin","phase":"begin"', 1)
        with self.assertRaises(v.ReceiptRejected):
            validate(rows)

    def test_torn_tail_blank_line_unicode_or_oversized_refused(self):
        good = serialize(success_records())
        for raw in (good[:-1], good + b"partial", good + b"\n",
                    good.replace(b"begin", b"\xffegin", 1),
                    good + b"x" * 65536,
                    b"",
                    b"not-a-json-document\n"):
            with self.subTest(length=len(raw)), self.assertRaises(v.ReceiptRejected):
                validate(raw)

    def test_invalid_json_types_and_extra_fields_refused(self):
        for bad in (True, "1794227100", None, 0):
            rows = success_records()
            rows[0]["t"] = bad
            with self.subTest(bad=bad), self.assertRaises(v.ReceiptRejected):
                validate(rows)
        rows = success_records()
        rows[0]["secret"] = "no-leak"
        with self.assertRaises(v.ReceiptRejected):
            validate(rows)
        rows = success_records()
        rows[2]["shared_plan"] = 7
        with self.assertRaises(v.ReceiptRejected):
            validate(rows)

    def test_repeated_begin_or_verified_and_time_backwards_refused(self):
        for extra in (success_records()[0], success_records()[6]):
            rows = success_records()
            rows.append(dict(extra))
            with self.assertRaises(v.ReceiptRejected):
                validate(rows)
        rows = success_records()
        rows[4]["t"] = STAMP - 1
        with self.assertRaises(v.ReceiptRejected):
            validate(rows)

    def test_closed_filename_is_not_sufficient_root_fs_evidence(self):
        with self.assertRaises(v.ReceiptRejected):
            validate(success_records(), closed_filename="malicious.journal.done-100")
        # The modeled receipt is pure bytes; it is never a claim that the file
        # was root-owned, fd-pinned, unique, or linked to live filesystem state.
        self.assertEqual(validate(success_records())["WRITER_EXCLUSION"], "NOT_ATTESTED")

    def test_no_execution_or_mutation_capabilities(self):
        source = SOURCE.read_text("utf-8")
        import ast
        module = ast.parse(source)
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                self.assertFalse(any(alias.name in {"os", "subprocess", "shutil"}
                                     for alias in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, {"os", "subprocess", "shutil"})
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"exec", "eval", "compile", "open",
                                                    "__import__", "breakpoint"})
        for bad in ("systemctl stop", "systemctl start", "subprocess.run(",
                    "os.unlink(", "os.rename(", "os.symlink(",
                    "os.replace(", "nft add", " --apply", "curl -", "git reset"):
            self.assertNotIn(bad, source)
        self.assertIn("SOURCE_ONLY_NO_HOST_ENTRYPOINT", source)


if __name__ == "__main__":
    unittest.main()
