import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest

OPS = pathlib.Path(__file__).resolve().parent / "operations"
sys.path.insert(0, str(OPS))
import elite_collect_staging_origin_receipt as col  # noqa: E402
import release_admission_receipts as ra  # noqa: E402
import release_receipt_store as store  # noqa: E402

SHA = "a" * 40
EXP = "platform-" + "b" * 12
NOW = 1_800_000_000
GOOD = "HTTP/2 200\r\nx-kmj-deploy-sha: " + SHA + "\r\ncontent-type: text/html\r\n\r\n"


class CollectorTests(unittest.TestCase):
    def test_exact_sha_yields_valid_receipt(self):
        r = col.make_receipt(SHA, EXP, NOW, lambda: ("200", GOOD))
        self.assertIsNone(ra.receipt_problem(r, SHA, EXP, NOW))
        self.assertEqual(r["kind"], "staging-origin")

    def test_wrong_or_missing_sha_non200_refused(self):
        for status, headers in (("200", GOOD.replace(SHA, "b" * 40)),
                                ("200", "HTTP/2 200\r\n\r\n"),
                                ("302", GOOD), ("500", GOOD)):
            with self.assertRaises(ValueError):
                col.make_receipt(SHA, EXP, NOW, lambda s=status, h=headers: (s, h))

    def test_write_is_private_atomic_and_readable_by_store(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o700)
            r = col.make_receipt(SHA, EXP, NOW, lambda: ("200", GOOD))
            p = col.write_receipt(r, d, os.getuid())
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertEqual([x.name for x in pathlib.Path(d).iterdir()], [p.name])
            got = store.read_protected(p, os.getuid())
            self.assertEqual(got, r)

    def test_write_refuses_open_directory(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o755)
            r = col.make_receipt(SHA, EXP, NOW, lambda: ("200", GOOD))
            with self.assertRaises(ValueError):
                col.write_receipt(r, d, os.getuid())
            self.assertEqual(list(pathlib.Path(d).iterdir()), [])

    def test_cli_write_blocked_off_elite_and_bad_input(self):
        self.assertEqual(col.main(["x", "--check", "short", EXP]), 2)
        self.assertEqual(col.main(["x", "--bogus", SHA, EXP]), 2)
        if os.geteuid() != 0:
            self.assertEqual(col.main(["x", "--write", SHA, EXP]), 2)

    def test_source_has_no_shell_or_production_touch(self):
        src = (OPS / "elite_collect_staging_origin_receipt.py").read_text()
        for bad in ("shell=True", "os.system", "/home/kmjprod", "systemctl", "production-release.json"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
