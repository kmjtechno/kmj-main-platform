import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "operations" / "diagnose-offsite-backup-unit-20261029.sh"


def run(log: str, args=()):
    """Run the diagnostic with stubbed systemctl/journalctl/id as root."""
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp)
        stubs = {
            "systemctl": "#!/bin/sh\ncase \"$*\" in *ExecMainStatus*) echo 255;; *Result*) echo exit-code;; *ActiveState*) echo '/root/private_key.pem';; *) echo ;; esac\n",
            "journalctl": f"#!/bin/sh\ncat <<'LOG'\n{log}\nLOG\n",
            "id": "#!/bin/sh\necho 0\n",
        }
        for name, body in stubs.items():
            path = bin_dir / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
        return subprocess.run(
            ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, check=False
        )


class DiagnoseOffsiteBackupUnit(unittest.TestCase):
    def test_classifies_ssh_auth_and_never_prints_journal_content(self):
        out = run(
            "sftp://user:hunter2@host.example/x\ntoken=abc123SECRET\n"
            "AGE-SECRET-KEY-1QQQQ\nuser@host: Permission denied (publickey)."
        )
        self.assertIn("failure_class=SSH_AUTH_KEY_REJECTED", out.stdout)
        for leaked in ("hunter2", "abc123SECRET", "AGE-SECRET-KEY", "host.example",
                       "Permission denied"):
            self.assertNotIn(leaked, out.stdout)
        self.assertIn("raw_output_suppressed=yes", out.stdout)
        self.assertIn("mutations=NONE", out.stdout)

    def test_rejects_any_argument(self):
        for args in (("other.service",), ("--unit", "x"), ("/tmp/receipt",)):
            result = run("x", args)
            self.assertEqual(result.returncode, 2)
            self.assertIn("BLOCKED=NO_ARGUMENTS_ACCEPTED", result.stdout)
            self.assertNotIn("failure_class", result.stdout)

    def test_does_not_read_executable_contents(self):
        code = SCRIPT.read_text()
        self.assertNotIn("exec_interpreter", code)
        self.assertNotRegex(code, r"\bhead\b[^\n]*\"\$exec_path\"")
        self.assertNotRegex(code, r"\bcat\b[^\n]*\$exec_path")

    def test_other_classes(self):
        cases = {
            "Host key verification failed.": "SSH_HOSTKEY",
            "ssh: connect to host x port 22: Connection timed out": "NETWORK_OR_REMOTE_DOWN",
            "Failed to copy: storageQuotaExceeded": "DISK_OR_REMOTE_QUOTA",
            "oauth2: invalid_grant": "REMOTE_AUTH_TOKEN",
            "something odd happened": "UNKNOWN_EXIT_255_NEEDS_LOG",
        }
        for line, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(f"failure_class={expected}", run(line).stdout)

    def test_script_is_read_only(self):
        code = "\n".join(
            line for line in SCRIPT.read_text().splitlines()
            if not line.lstrip().startswith("#")
        )
        forbidden = [
            r"\bsystemctl\s+(start|stop|restart|reload|enable|disable|kill|daemon-reload)",
            r"(^|[;&|\s])rm\s", r"\brclone\s+(copy|sync|delete|move|purge)",
            r"(^|[;&|(]\s*)(ssh|sftp|scp|curl|wget|nc)\s", r"\bchmod\b", r"\bchown\b",
            r"\bcat\s+/etc", r"\bmv\s", r"\bsed\s+-i",
        ]
        import re
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, code), pattern)


    def test_sensitive_systemd_metadata_never_read_or_printed(self):
        code = SCRIPT.read_text()
        for forbidden in (
            "kv exec_path", "kv working_directory", "kv run_as_user",
            "show ExecStart", "show EnvironmentFiles", "show WorkingDirectory",
            "show User", "ssh_file:", "getent passwd",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        self.assertIn("kv metadata_paths_exposed no", code)
        result = run("nothing special")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("/root/private_key.pem", result.stdout)
        self.assertIn("active_state=unknown/", result.stdout)

    def test_systemd_show_properties_fixed_allowlist(self):
        import re
        code = SCRIPT.read_text()
        queried = set(re.findall(r"\\bshow(?:_enum)?\\s+([A-Za-z]+)", code))
        self.assertEqual(
            queried,
            {"LoadState", "ActiveState", "SubState", "Result", "ExecMainStatus"},
        )


if __name__ == "__main__":
    unittest.main()
