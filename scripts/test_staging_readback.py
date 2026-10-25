from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parent / "operations" / "check-staging-readback.py"
spec = importlib.util.spec_from_file_location("readback", MODULE)
assert spec and spec.loader
readback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readback)

SHA = "a" * 40
GOOD = "HTTP/2 200\r\nx-kmj-deploy-sha: " + SHA + "\r\ncontent-type: text/html\r\n\r\n"


class StageReadbackTests(unittest.TestCase):
    def test_valid_exact_sha(self):
        self.assertEqual(readback.check_readback(SHA, GOOD, "200"), SHA)

    def test_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            readback.check_readback("b" * 40, GOOD, "200")

    def test_absent_and_duplicate_headers_rejected(self):
        for raw in ("HTTP/2 200\r\n\r\n", GOOD.replace("content-type", "X-KMJ-DEPLOY-SHA")):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    readback.check_readback(SHA, raw, "200")

    def test_old_proxy_header_cannot_override_final_response(self):
        proxy = "HTTP/1.1 200 Connection established\r\nx-kmj-deploy-sha: " + SHA + "\r\n\r\n"
        with self.assertRaises(ValueError):
            readback.check_readback(SHA, proxy + "HTTP/2 200\r\n\r\n", "200")

    def test_non_200_and_non_full_sha_rejected(self):
        for candidate, status in ((SHA, "302"), (SHA[:-1], "200"), ("z" * 40, "200")):
            with self.subTest(candidate=candidate, status=status):
                with self.assertRaises(ValueError):
                    readback.check_readback(candidate, GOOD, status)

    def test_readback_requires_successful_real_staging_deploy_not_just_source_promotion(self):
        # This job must not run merely because CI promoted a branch: the
        # physical staging deployment is separately guarded and may be absent.
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "staging-exact-sha-readback.yml").read_text(encoding="utf-8")
        self.assertIn("workflows: ['Staging VPS Deploy']", workflow)
        self.assertNotIn("workflows: ['Staging Promotion Gate']", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertNotIn("github.event.workflow_run.event == 'push'", workflow)
        self.assertIn("test \"$sha\" = \"$PROMOTED_SHA\"", workflow)
        self.assertIn("check-staging-readback.py", workflow)
        self.assertIn("https://staging.kmjtechno.com", workflow)


if __name__ == "__main__":
    unittest.main()
