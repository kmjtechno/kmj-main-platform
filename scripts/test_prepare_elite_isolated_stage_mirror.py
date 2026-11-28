import importlib.util
import json
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "operations" / "prepare-elite-isolated-stage-mirror-20261128.py"
spec = importlib.util.spec_from_file_location("stage_mirror", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class StageMirrorTests(unittest.TestCase):
    def test_secret_and_mutable_exclusions(self):
        for name, rel in ((".env", ".env"), (".env.production", ".env.production"),
                          ("storage", "storage"), ("cache", "bootstrap/cache"),
                          ("bin", "vendor/bin"), ("key.pem", "config/key.pem"),
                          (".git", ".git"), ("node_modules", "node_modules")):
            self.assertFalse(mod.approved_name(name, rel))
        self.assertTrue(mod.approved_name("index.php", "public/index.php"))
        self.assertTrue(mod.approved_name("manifest.json", "public/build/manifest.json"))
        compile(mod.DIGEST_PROGRAM, "<sealed-tree>", "exec")

    def test_dual_mirror_checks_assets_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            code, public = root / "code", root / "public"
            for base in (code / "public", public):
                (base / "build/assets").mkdir(parents=True)
                (base / "index.php").write_bytes(b"entry")
                (base / "build/assets/test.js").write_bytes(b"chunk")
                (base / "build/manifest.json").write_text(json.dumps({
                    "resources/js/pages/services/codebridge-workspace.tsx": {"file": "assets/test.js"}
                }))
            mod.public_manifest_check(code, public)
            (public / "index.php").write_bytes(b"changed")
            with self.assertRaises(SystemExit):
                mod.public_manifest_check(code, public)

    def test_exact_candidate_and_live_binding(self):
        self.assertEqual(mod.SHA, "710c6f3ca10310457bc7243caabc0e48476ec110")
        self.assertEqual(mod.OLD_PROD, "platform-72e7c9ada190")
        self.assertEqual(mod.SOURCE, pathlib.Path("/home/kmjstage/releases") / mod.SHA / "apps/platform")


if __name__ == "__main__":
    unittest.main()
