"""Fixture tests for the 4-lineage certbot matrix guard (no root, no real /etc)."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).with_name("KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261126.py")
spec = importlib.util.spec_from_file_location("kmj_v3_onepass_4l", SRC)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

# Stand-in for the installed publisher: only the two names the guard uses.
PUBLISHER = b"""
CERTBOT_FILES=("cert.pem","chain.pem","fullchain.pem","privkey.pem")
def certbot_link_target(rootfd,fd,relative_dir,name,allowed):
    return ("t","d")
"""
FILES = ("cert.pem", "chain.pem", "fullchain.pem", "privkey.pem")


def build(root: Path, links: tuple[str, ...], regular: tuple[str, ...]):
    live = root / "live"
    live.mkdir(mode=0o700)
    (live / "README").write_text("x")
    for name in links:
        d = live / name
        d.mkdir(mode=0o755)
        for f in FILES:
            os.symlink(f"../../archive/{name}/{f[:-4]}1.pem", d / f)
    for name in regular:
        d = live / name
        d.mkdir(mode=0o700)
        for f in FILES:
            (d / f).write_text("pem")


class MatrixTest(unittest.TestCase):
    def check(self, links, regular):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "le"
            root.mkdir(mode=0o755)
            build(root, links, regular)
            old = h.CONFIG["letsencrypt"]
            h.CONFIG["letsencrypt"] = root
            try:
                return h.validate_certbot_live_matrix(PUBLISHER, expected_uid=os.getuid())
            finally:
                h.CONFIG["letsencrypt"] = old

    def test_four_lineages_pass(self):
        self.assertEqual(
            self.check(("cloudos.x", "staging.x", "mail.x"), ("main.x",)), 16
        )

    def test_old_three_lineage_shape_now_fails_closed(self):
        with self.assertRaises(h.Deny) as ctx:
            self.check(("cloudos.x", "staging.x"), ("main.x",))
        self.assertEqual(str(ctx.exception), "CERTBOT_MIXED_SOURCE_MATRIX_DRIFT")

    def test_fifth_lineage_fails_closed(self):
        with self.assertRaises(h.Deny) as ctx:
            self.check(("a.x", "b.x", "c.x", "d.x"), ("main.x",))
        self.assertEqual(str(ctx.exception), "CERTBOT_MIXED_SOURCE_MATRIX_DRIFT")

    def test_group_writable_lineage_is_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "le"
            root.mkdir(mode=0o755)
            build(root, ("cloudos.x", "staging.x", "mail.x"), ("main.x",))
            os.chmod(root / "live" / "mail.x", 0o775)
            old = h.CONFIG["letsencrypt"]
            h.CONFIG["letsencrypt"] = root
            try:
                with self.assertRaises(h.Deny) as ctx:
                    h.validate_certbot_live_matrix(PUBLISHER, expected_uid=os.getuid())
            finally:
                h.CONFIG["letsencrypt"] = old
            self.assertEqual(str(ctx.exception), "CERTBOT_LIVE_LINEAGE_UNTRUSTED")


if __name__ == "__main__":
    unittest.main()
