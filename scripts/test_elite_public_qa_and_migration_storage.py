import os
import pathlib
import sys
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import elite_collect_public_qa_receipt as qa  # noqa: E402
import elite_derive_migration_storage_receipt as ms  # noqa: E402
import release_admission_receipts as ra  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12
NOW = 1_800_000_000
GOOD = "HTTP/2 200\r\nx-kmj-deploy-sha: " + SHA + "\r\n\r\n"


def part(kind, **over):
    r = {"schema": ra.RECEIPT_SCHEMA, "kind": kind, "host": "kmj-elite", "approvedSha": SHA,
         "expectedCurrentRelease": EXP, "capturedAt": NOW - 5, "result": "pass",
         "artifactSha256": ("1" if kind == "rollback-rehearsal" else "2") * 64}
    r.update(over)
    return r


class PublicQaTests(unittest.TestCase):
    def test_all_routes_exact_sha_pass(self):
        seen = []
        r = qa.make_receipt(SHA, EXP, NOW, lambda route: (seen.append(route), ("200", GOOD))[1])
        self.assertEqual(tuple(seen), qa.ROUTES)
        self.assertIsNone(ra.receipt_problem(r, SHA, EXP, NOW))

    def test_any_bad_route_fails(self):
        for bad_route in qa.ROUTES:
            def fetch(route, b=bad_route):
                return ("302", GOOD) if route == b else ("200", GOOD)
            with self.assertRaises(ValueError):
                qa.make_receipt(SHA, EXP, NOW, fetch)
        with self.assertRaises(ValueError):
            qa.make_receipt(SHA, EXP, NOW, lambda route: ("200", GOOD.replace(SHA, "c" * 40)))

    def test_cli_guards(self):
        self.assertEqual(qa.main(["x", "--check", "bad", EXP]), 2)
        if os.geteuid() != 0:
            self.assertEqual(qa.main(["x", "--write", SHA, EXP]), 2)


class MigrationStorageTests(unittest.TestCase):
    def parts(self):
        return [part("rollback-rehearsal"), part("disposable-restore")]

    def test_both_parts_derive_valid_receipt(self):
        r = ms.derive(self.parts(), SHA, EXP, NOW)
        self.assertIsNone(ra.receipt_problem(r, SHA, EXP, NOW))
        self.assertEqual(r["kind"], "migration-storage")

    def test_missing_stale_failed_duplicate_part_refused(self):
        cases = [self.parts()[:1], self.parts()[1:],
                 [part("rollback-rehearsal", capturedAt=NOW - 10**6), part("disposable-restore")],
                 [part("rollback-rehearsal", result="fail"), part("disposable-restore")],
                 [part("rollback-rehearsal", approvedSha="d" * 40), part("disposable-restore")],
                 self.parts() + [part("disposable-restore")], []]
        for c in cases:
            with self.assertRaises(ValueError):
                ms.derive(c, SHA, EXP, NOW)

    def test_cli_guards(self):
        self.assertEqual(ms.main(["x", "--nope", SHA, EXP]), 2)
        if os.geteuid() != 0:
            self.assertEqual(ms.main(["x", "--write", SHA, EXP]), 2)


if __name__ == "__main__":
    unittest.main()
