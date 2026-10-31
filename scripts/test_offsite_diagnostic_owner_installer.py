"""Synthetic owner-installer checks: never execute privileged installation."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
INSTALLER = ROOT / "operations/install-offsite-diagnostic-owner-20261031.sh"
DIAGNOSTIC = ROOT / "operations/diagnose-offsite-backup-unit-20261029.sh"
PIN = "3ac8127f8e66ac4579330ae7671c2a2b31f68f6865c2a7c67e376adb475f6e32"


def run(path, mode):
    return subprocess.run(
        ["/bin/bash", "-p", str(path), mode], capture_output=True, text=True, timeout=8
    )


class OffsiteDiagnosticInstallerTests(unittest.TestCase):
    def test_syntax_and_source_pin(self):
        subprocess.run(["bash", "-n", str(INSTALLER)], check=True, timeout=8)
        self.assertEqual(hashlib.sha256(DIAGNOSTIC.read_bytes()).hexdigest(), PIN)
        source = INSTALLER.read_text()
        self.assertIn(PIN, source)
        self.assertIn("KMJ_OFFSITE_BACKUP=NOT_VERIFIED", source)

    def test_inspect_is_nonmutating_and_source_pinned(self):
        result = run(INSTALLER, "--inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("KMJ_OFFSITE_DIAGNOSTIC_INSTALL=INSPECT_ONLY", result.stdout)
        self.assertNotIn("PINNED_INACTIVE_ONLY", result.stdout)

    def test_rejects_tampered_file_and_symlink(self):
        with tempfile.TemporaryDirectory(prefix="kmj-offsite-install-") as tmp:
            location = Path(tmp)
            installer = location / INSTALLER.name
            diagnostic = location / DIAGNOSTIC.name
            shutil.copyfile(INSTALLER, installer)
            shutil.copyfile(DIAGNOSTIC, diagnostic)
            diagnostic.write_bytes(diagnostic.read_bytes() + b"\n# changed\n")
            result = run(installer, "--inspect")
            self.assertEqual(result.returncode, 2)
            self.assertIn("BLOCKED_SOURCE_HASH", result.stdout)
            diagnostic.unlink()
            diagnostic.symlink_to(DIAGNOSTIC)
            result = run(installer, "--inspect")
            self.assertEqual(result.returncode, 2)
            self.assertIn("BLOCKED_SOURCE_MISSING_OR_SYMLINK", result.stdout)

    def test_operator_mode_cannot_install_on_ci_host(self):
        with tempfile.TemporaryDirectory(prefix="kmj-offsite-install-") as tmp:
            location = Path(tmp)
            installer = location / INSTALLER.name
            diagnostic = location / DIAGNOSTIC.name
            shutil.copyfile(INSTALLER, installer)
            shutil.copyfile(DIAGNOSTIC, diagnostic)
            result = run(installer, "--install")
            self.assertEqual(result.returncode, 2)
            self.assertTrue(
                "BLOCKED_OWNER_HOST" in result.stdout
                or "BLOCKED_IMMUTABLE_SOURCE_PATH" in result.stdout
            )

    def test_privileged_shell_and_fixed_binary_path(self):
        source = INSTALLER.read_text()
        self.assertTrue(source.startswith("#!/bin/bash -p\\n"))
        self.assertIn("PATH=/usr/sbin:/usr/bin:/sbin:/bin", source)
        self.assertIn("block PRIVILEGED_SHELL_REQUIRED", source)
        for path in ("/usr", "/usr/local", "/usr/local/libexec"):
            self.assertIn(path, source)

        ordinary = subprocess.run(
            ["/bin/bash", str(INSTALLER), "--inspect"],
            capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(ordinary.returncode, 2)
        self.assertIn("BLOCKED_PRIVILEGED_SHELL_REQUIRED", ordinary.stdout)

    def test_hostile_path_and_bashenv_never_execute_in_privileged_mode(self):
        with tempfile.TemporaryDirectory(prefix="kmj-offsite-hostile-") as tmp:
            directory = Path(tmp)
            sentinel = directory / "executed"
            for name in ("sha256sum", "dirname", "cut", "hostname", "install"):
                fake = directory / name
                fake.write_text(
                    "#!/bin/sh\\n/bin/printf hacked > " + str(sentinel) + "\\n"
                )
                fake.chmod(0o755)
            bashenv = directory / "injected-bashenv"
            bashenv.write_text(
                "/bin/printf hacked > " + str(sentinel) + "\\n"
            )
            env = os.environ.copy()
            env["PATH"] = str(directory)
            env["BASH_ENV"] = str(bashenv)
            result = subprocess.run(
                ["/bin/bash", "-p", str(INSTALLER), "--inspect"],
                env=env, capture_output=True, text=True, timeout=8,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("INSPECT_ONLY", result.stdout)
            self.assertFalse(sentinel.exists())

    def test_atomic_nonclobber_and_no_runtime_mutation(self):
        source = INSTALLER.read_text()
        for term in (
            "ln -T --",
            "block TARGET_EXISTS_OR_LINK_FAILED",
            "block EXISTING_TARGET_REQUIRES_REVIEW",
            "block SOURCE_CHAIN",
            "block SOURCE_OWNER",
            "block SOURCE_PERMISSIONS",
            "block TARGET_HASH",
            "KMJ_OFFSITE_DIAGNOSTIC_EXECUTION=NOT_ATTEMPTED",
            "KMJ_PRODUCTION=UNCHANGED",
        ):
            self.assertIn(term, source)
        for prohibited in (
            "systemctl start", "systemctl restart", "systemctl enable",
            "git reset", "git clean", "curl ", "wget ", "ssh ", "sudo ",
            "rm -rf", "chmod -R", "chown -R",
        ):
            self.assertNotIn(prohibited, source)
        self.assertLess(source.index("block OWNER_HOST"), source.index('tmp="$(mktemp'))


if __name__ == "__main__":
    unittest.main()
