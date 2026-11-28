import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1] / "scripts/operations/repair-elite-staging-final-path-views-20261128.py"
spec = importlib.util.spec_from_file_location("view_repair", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RepairTests(unittest.TestCase):
    def test_atomic_exchange_preserves_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"a", Path(tmp)/"b"
            a.mkdir()
            b.mkdir()
            (a/"old").write_text("old")
            (b/"new").write_text("new")
            m.exchange(a,b)
            self.assertEqual((a/"new").read_text(),"new")
            self.assertEqual((b/"old").read_text(),"old")
            m.exchange(a,b)
            self.assertEqual((a/"old").read_text(),"old")

    def test_read_rejects_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b = Path(tmp)/"a",Path(tmp)/"b"
            a.write_text("x")
            b.symlink_to(a)
            with self.assertRaises(OSError):
                m.read_file(b,os.getuid(),10,protected=False)
            b.unlink()
            os.link(a,b)
            with self.assertRaisesRegex(ValueError,"FILE_METADATA"):
                m.read_file(a,os.getuid(),10,protected=False)

    def test_copy_preserves_compiler_timestamps_and_readonly_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst = Path(tmp)/"src",Path(tmp)/"dst"
            src.mkdir()
            dst.mkdir()
            p = src/("a"*32+".php")
            p.write_text("<?php echo 1;")
            os.chmod(p,0o600)
            with patch.object(m,"command",return_value=b""):
                self.assertEqual(m.copy_views(src,dst,os.getuid()),1)
            q = dst/p.name
            self.assertEqual(q.read_bytes(),p.read_bytes())
            self.assertEqual(q.stat().st_mtime_ns,p.stat().st_mtime_ns)
            self.assertEqual(q.stat().st_mode & 0o777,0o444)

    def test_reject_unexpected_generated_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst = Path(tmp)/"src",Path(tmp)/"dst"
            src.mkdir()
            dst.mkdir()
            (src/"unexpected.php").write_text("x")
            with self.assertRaisesRegex(ValueError,"VIEW_NAME"):
                m.copy_views(src,dst,os.getuid())
            self.assertEqual(list(dst.iterdir()),[])

    def test_compile_bootstrap_uses_console_kernel_not_http(self):
        self.assertIn(r"Illuminate\Contracts\Console\Kernel::class", m.PHP_COMPILE)
        self.assertNotIn(r"Illuminate\Contracts\Http\Kernel::class", m.PHP_COMPILE)
        self.assertIn("$app->bound('request')", m.PHP_COMPILE)
        self.assertIn("$kernel->call('view:cache')", m.PHP_COMPILE)
        self.assertIn(r"Illuminate\Contracts\Http\Kernel::class", m.PHP_HEALTH)

    def test_health_template_uses_actual_lexical_path(self):
        self.assertIn("'/../resources/health-up.blade.php'",m.PHP_COMPILE)
        self.assertIn("'/../resources/health-up.blade.php'",m.PHP_HEALTH)
        self.assertIn("view:cache",m.PHP_COMPILE)
        self.assertIn("isExpired($source)",m.PHP_HEALTH)
        self.assertIn("VIEW_COMPILED_PATH",m.PHP_COMPILE)
        self.assertNotIn("laravel::health-up",m.PHP_COMPILE)


if __name__ == "__main__":
    unittest.main()
