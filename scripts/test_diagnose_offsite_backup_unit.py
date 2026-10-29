import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "operations" / "diagnose-offsite-backup-unit-20261029.sh"


def run(log: str):
    """Run the diagnostic with stubbed systemctl/journalctl/id as root."""
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp)
        stubs = {
            "systemctl": "#!/bin/sh\ncase \"$*\" in *ExecMainStatus*) echo 255;; *Result*) echo exit-code;; *) echo ;; esac\n",
            "journalctl": f"#!/bin/sh\ncat <<'LOG'\n{log}\nLOG\n",
            "id": "#!/bin/sh\necho 0\n",
        }
        for name, body in stubs.items():
            path = bin_dir / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
        return subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False
        )


class DiagnoseOffsiteBackupUnit(unittest.TestCase):
    def test_classifies_ssh_auth_and_redacts_secrets(self):
        out = run(
            "sftp://user:hunter2@host.example/x\ntoken=abc123SECRET\n"
            "user@host: Permission denied (publickey)."
        )
        self.assertIn("failure_class=SSH_AUTH_KEY_REJECTED", out.stdout)
        for secret in ("hunter2", "abc123SECRET"):
            self.assertNotIn(secret, out.stdout)
        self.assertIn("mutations=NONE", out.stdout)

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


if __name__ == "__main__":
    unittest.main()
