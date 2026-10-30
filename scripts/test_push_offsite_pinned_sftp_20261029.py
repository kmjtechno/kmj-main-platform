#!/usr/bin/env python3
"""Stub-driven tests for the pinned-SFTP offsite push (no network, no root)."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "operations/push-offsite-39b88b36d071-pinned-sftp-20261029.sh"
PIN = "SHA256:" + "A" * 43
CONF = f"HOST=backup.example\nPORT=22\nUSER=kmjbackup\nREMOTE_DIR=/incoming\nIDENTITY_FILE=@IDENT@\nHOSTKEY_SHA256={PIN}\n"


class Env:
    def __init__(self, root: Path, *, fingerprint=PIN, sftp_mode="ok", conf=CONF, remote=None):
        self.root = root
        (root / "bin").mkdir()
        (root / "backups").mkdir()
        self.remote = root / "remote"
        self.remote.mkdir()
        if remote is not None:
            (self.remote / "offsite-39b88b36d071.tar.gz.age").write_bytes(remote)
        self.local = root / "backups/offsite-39b88b36d071.tar.gz.age"
        self.local.write_bytes(b"ENCRYPTED-TEST-BYTES")
        ident = root / "identity"
        ident.write_text("KEY")
        conf_path = root / "offsite-sftp.conf"
        conf_path.write_text(conf.replace("@IDENT@", str(ident)))
        self.sftp_log = root / "sftp.log"
        stubs = {
            "id": "#!/bin/sh\necho 0\n",
            # Pretend every protected file is root:0600:1 link.
            "stat": "#!/bin/sh\ncase \"$*\" in *'%u:%a:%h'*) echo 0:600:1;; *\"-c %u -- \"*) echo 0;; *) exec /usr/bin/stat \"$@\";; esac\n",
            "ssh-keyscan": "#!/bin/sh\necho 'backup.example ssh-ed25519 AAAAFAKEKEY'\n",
            "ssh-keygen": f"#!/bin/sh\necho '256 {fingerprint} backup.example (ED25519)'\n",
            "sftp": self._sftp(sftp_mode),
        }
        for name, body in stubs.items():
            path = root / "bin" / name
            path.write_text(body)
            path.chmod(0o755)
        text = SCRIPT.read_text()
        text = text.replace("CONF=/etc/kmj-codebridge/offsite-sftp.conf", f"CONF={conf_path}")
        text = text.replace("LOCAL=/var/backups/kmj-platform/offsite-39b88b36d071.tar.gz.age", f"LOCAL={self.local}")
        text = text.replace("BACKUP_DIR=/var/backups/kmj-platform", f"BACKUP_DIR={root}/backups")
        self.script = root / "push.sh"
        self.script.write_text(text)
        conf_path.chmod(0o600)

    def _sftp(self, mode: str) -> str:
        r = self.remote
        return f"""#!/bin/sh
batch=''
all="$*"
while [ $# -gt 0 ]; do case "$1" in -b) batch=$2; shift;; esac; shift; done
echo "$all" >> {self.root}/sftp.log
cat "$batch" >> {self.root}/sftp.log
case "{mode}" in
  auth) echo 'user@host: Permission denied (publickey).' >&2; exit 255;;
  net) echo 'ssh: connect to host x port 22: Connection timed out' >&2; exit 255;;
esac
map() {{ case "$1" in /incoming/*) echo "{r}/${{1#/incoming/}}";; *) echo "$1";; esac; }}
while read -r cmd a b c; do
  a=$(map "$a"); b=$(map "$b")
  case "$cmd" in
    get) if [ -f "$a" ]; then cp "$a" "$b"; else echo "File \\"$a\\" not found." >&2; exit 1; fi ;;
    put) case "{mode}" in corrupt) echo corrupt > "$b";; quota) echo 'Failure: No space left' >&2; exit 1;; *) cp "$a" "$b";; esac ;;
    ln) if [ -e "$b" ]; then echo 'Couldn'"'"'t link: Failure' >&2; exit 1; fi; ln "$a" "$b" ;;
    rm) rm -f "$a" ;;
    -rm) rm -f "$a" ;;
  esac
done < "$batch"
"""

    def run(self):
        env = dict(os.environ, PATH=f"{self.root}/bin:{os.environ['PATH']}")
        return subprocess.run(["bash", str(self.script)], env=env, capture_output=True, text=True)


class PinnedSftpPush(unittest.TestCase):
    def go(self, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(Path(tmp), **kw)
            result = env.run()
            leftovers = [p.name for p in (Path(tmp) / "backups").iterdir() if p.name.startswith(".kmj-offsite-push")]
            uploaded = (env.remote / "offsite-39b88b36d071.tar.gz.age")
            return result, uploaded.read_bytes() if uploaded.exists() else None, leftovers, env.sftp_log.read_text() if env.sftp_log.exists() else ""

    def test_success_uploads_atomically_and_verifies_readback(self):
        r, uploaded, left, log = self.go()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("HOSTKEY_PIN=PASS", r.stdout)
        self.assertIn("SFTP_UPLOAD=PASS", r.stdout)
        self.assertIn("REMOTE_READBACK_SHA256=PASS", r.stdout)
        self.assertIn("OFFSITE_RESTORE=NOT_VERIFIED", r.stdout)
        self.assertEqual(uploaded, b"ENCRYPTED-TEST-BYTES")
        self.assertEqual(left, [])
        self.assertIn(".incoming-offsite-39b88b36d071.tar.gz.age.", log)
        self.assertRegex(log, r"ln .*\.incoming-")
        self.assertNotIn("rename ", log)
        for flag in ("BatchMode=yes", "IdentitiesOnly=yes", "StrictHostKeyChecking=yes",
                     "PasswordAuthentication=no", "IdentityAgent=none"):
            self.assertIn(flag, log)

    def test_wrong_host_key_fails_before_any_sftp(self):
        r, uploaded, _, log = self.go(fingerprint="SHA256:" + "B" * 43)
        self.assertEqual(r.returncode, 1)
        self.assertIn("HOSTKEY_PIN=MISMATCH", r.stdout)
        self.assertEqual(log, "")
        self.assertIsNone(uploaded)

    def test_auth_failure_is_classified_not_printed(self):
        r, _, _, _ = self.go(sftp_mode="auth")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SFTP_UPLOAD=FAIL:SSH_AUTH_KEY_REJECTED", r.stdout)
        self.assertNotIn("publickey", r.stdout + r.stderr)

    def test_network_failure_classified(self):
        r, *_ = self.go(sftp_mode="net")
        self.assertIn("FAIL:NETWORK_OR_REMOTE_DOWN", r.stdout)

    def test_existing_identical_object_is_accepted_only_after_readback(self):
        r, uploaded, left, _ = self.go(remote=b"ENCRYPTED-TEST-BYTES")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("REMOTE_COMMIT_NO_CLOBBER=TARGET_EXISTS_OR_FAILED", r.stdout)
        self.assertIn("REMOTE_READBACK_SHA256=PASS", r.stdout)
        self.assertEqual(uploaded, b"ENCRYPTED-TEST-BYTES")

    def test_existing_different_object_is_never_overwritten(self):
        r, uploaded, left, _ = self.go(remote=b"OTHER")
        self.assertEqual(r.returncode, 1)
        self.assertIn("REMOTE_READBACK=DIGEST_MISMATCH", r.stdout)
        self.assertNotIn("OFFSITE_PUSH=PASS", r.stdout)
        self.assertEqual(uploaded, b"OTHER")

    def test_incoming_names_are_unique_per_run_and_cleaned_after_losing_the_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(Path(tmp), remote=b"OTHER")
            env.run()
            leftovers = [p.name for p in env.remote.iterdir() if p.name.startswith(".incoming-")]
            self.assertEqual(leftovers, [])
            first = env.sftp_log.read_text()
            env.sftp_log.unlink()
            env.run()
            second = env.sftp_log.read_text()
            names = lambda t: set(re.findall(r"\.incoming-[^ \n]+", t))
            self.assertTrue(names(first) and names(second))
            self.assertTrue(names(first).isdisjoint(names(second)))

    def test_lock_does_not_create_or_follow_files_in_shared_lock_dirs(self):
        text = SCRIPT.read_text()
        self.assertNotIn("/run/lock", text)
        self.assertNotRegex(text, r"exec 9>")
        self.assertIn('exec 9<"$BACKUP_DIR"', text)
        self.assertIn("protected_chain", text)

    def test_readback_digest_mismatch_fails(self):
        r, *_ = self.go(sftp_mode="corrupt")
        self.assertEqual(r.returncode, 1)
        self.assertIn("REMOTE_READBACK=DIGEST_MISMATCH", r.stdout)

    def test_bad_config_values_are_blocked(self):
        for bad in (CONF.replace("HOST=backup.example", "HOST=a;rm -rf /"),
                    CONF.replace("REMOTE_DIR=/incoming", "REMOTE_DIR=/in/../etc"),
                    CONF.replace("PORT=22", "PORT=70000"),
                    CONF.replace(PIN, "SHA256:short"),
                    CONF + "EXTRA=1\n", CONF + "HOST=dup\n"):
            with self.subTest(bad=bad[:40]):
                r, *_ = self.go(conf=bad)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertIn("OFFSITE_PUSH=BLOCKED", r.stdout)

    def test_arguments_rejected_and_script_never_prints_secrets_or_sources_config(self):
        text = SCRIPT.read_text()
        self.assertNotRegex(text, r"(^|\n)\s*(source|\.)\s+\"?\$CONF")
        self.assertNotIn("cat \"$ident\"", text)
        self.assertNotIn("StrictHostKeyChecking=no", text)
        self.assertNotIn("StrictHostKeyChecking=accept-new", text)
        self.assertNotRegex(text, r"ssh-keyscan[^\n]*>>\s*/root")
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(Path(tmp))
            e = dict(os.environ, PATH=f"{tmp}/bin:{os.environ['PATH']}")
            r = subprocess.run(["bash", str(env.script), "x"], env=e, capture_output=True, text=True)
            self.assertIn("NO_ARGUMENTS_ACCEPTED", r.stdout)


    def test_real_openssh_hardlink_never_replaces_existing_object(self):
        import shutil
        server = Path("/usr/lib/openssh/sftp-server")
        if not shutil.which("sftp") or not server.is_file():
            self.skipTest("Real OpenSSH sftp client/server not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming, final = root / "incoming", root / "final"
            incoming.write_bytes(b"NEW")
            final.write_bytes(b"EXISTING")
            batch = root / "batch"
            batch.write_text(f'ln "{incoming}" "{final}"\n')
            result = subprocess.run(["sftp", "-D", str(server), "-b", str(batch)],
                                    capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(final.read_bytes(), b"EXISTING")
            self.assertEqual(incoming.read_bytes(), b"NEW")
            final.unlink()
            result = subprocess.run(["sftp", "-D", str(server), "-b", str(batch)],
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(final.read_bytes(), b"NEW")
            self.assertEqual(incoming.read_bytes(), b"NEW")
            self.assertEqual(final.stat().st_ino, incoming.stat().st_ino)

if __name__ == "__main__":
    unittest.main()
