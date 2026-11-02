#!/usr/bin/env python3
"""Release-neutral Google SFTP restore script: argument validation, metadata binding, no pins. No live access."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "operations/verify-main-platform-google-sftp-restore-20261030.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")
META = re.search(r"python3 - \"\$tmp/extracted/metadata.txt\" \"\$expected_source_sha\" \"\$candidate_sha\" \"\$expected_release\" <<'PY'\n(.*?)\nPY\n", SOURCE, re.S).group(1)
SHA = "a" * 40
REL = "platform-" + "b" * 12
SRC = "c" * 64


def run(*args: str, env=None):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env or dict(os.environ))


def meta(lines: list[str], sha=SHA, rel=REL, src=SRC) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "metadata.txt"
        p.write_text("\n".join(lines) + "\n", encoding="ascii")
        return subprocess.run(["python3", "-c", META, str(p), src, sha, rel]).returncode


GOOD = [
    "backup_kind=offsite_sanitized_local_witness",
    f"source_local_sha256={SRC}",
    f"target_sha={SHA}",
    f"current_release={REL}",
    "production_env_excluded=YES",
]


class ReleaseNeutralRestore(unittest.TestCase):
    def test_syntax_and_no_pinned_release(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        for pinned in ("39b88b36d071", "574e443a2c75", "bbf95ca55df0b031"):
            self.assertNotIn(pinned, SOURCE)

    def test_arguments_are_validated_before_any_host_or_filesystem_check(self):
        bad = [
            (), ("--candidate-sha", SHA), (SHA, REL), ("--expected-release", REL, "--candidate-sha", SHA),
            ("--candidate-sha", SHA, "--expected-release", REL, "extra"),
        ]
        for args in bad:
            r = run(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("USAGE_CANDIDATE_SHA_AND_EXPECTED_RELEASE_ONLY=BLOCKED", r.stdout)
        for sha in (SHA.upper(), SHA[:-1], SHA + "0", "../" + SHA[:37], SHA[:39] + "g", SHA[:39] + "\n", ""):
            r = run("--candidate-sha", sha, "--expected-release", REL)
            self.assertEqual(r.returncode, 2, sha)
            self.assertIn("CANDIDATE_SHA_INVALID=BLOCKED", r.stdout)
        for rel in ("platform-" + "b" * 11, "platform-" + "B" * 12, "../platform-" + "b" * 12, "release-" + "b" * 12, "platform-" + "b" * 12 + "/x", ""):
            r = run("--candidate-sha", SHA, "--expected-release", rel)
            self.assertEqual(r.returncode, 2, rel)
            self.assertIn("EXPECTED_RELEASE_INVALID=BLOCKED", r.stdout)

    def test_valid_arguments_pass_validation_and_stop_at_operator_gate(self):
        r = run("--candidate-sha", SHA, "--expected-release", REL)
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stdout, r"NONROOT_INFO_REQUIRED=BLOCKED|GOOGLE_RECOVERY_HOST_REQUIRED=BLOCKED")

    def test_metadata_binding_accepts_only_the_exact_candidate(self):
        self.assertEqual(meta(GOOD), 0)
        self.assertNotEqual(meta(GOOD, sha="d" * 40), 0)  # old/other candidate
        self.assertNotEqual(meta(GOOD, rel="platform-" + "e" * 12), 0)  # other active release
        self.assertNotEqual(meta(GOOD, src="f" * 64), 0)  # other source archive digest
        self.assertNotEqual(meta(GOOD + ["extra=1"]), 0)
        self.assertNotEqual(meta(GOOD + [GOOD[0]]), 0)  # duplicate key
        self.assertNotEqual(meta([l for l in GOOD if "env_excluded" not in l]), 0)
        self.assertNotEqual(meta([l.replace("=YES", "=NO") for l in GOOD]), 0)
        self.assertNotEqual(meta(GOOD[:-1] + ["garbage-without-equals"]), 0)

    def test_expected_hashes_come_from_validated_environment_only(self):
        self.assertIn('[[ "$expected_source_sha" =~ ^[0-9a-f]{64}$ ]] || block EXPECTED_SOURCE_LOCAL_SHA256', SOURCE)
        self.assertIn("KMJ_EXPECTED_ENCRYPTED_SHA256", SOURCE)
        self.assertIn('encrypted="$HOME/kmj-recovery-scratch/offsite-$short_sha.tar.gz.age"', SOURCE)

    def test_storage_tar_extract_uses_same_no_network_bwrap_boundary(self):
        # Untrusted tar extraction must not run on the host outside bwrap.
        self.assertIn("--unshare-all --die-with-parent --new-session --cap-drop ALL", SOURCE)
        self.assertIn("--ro-bind / /", SOURCE)
        self.assertIn('--tmpfs "$HOME" --bind "$tmp" "$tmp"', SOURCE)
        self.assertIn('if ! "${sandbox[@]}" tar -xzf "$tmp/extracted/storage.tar.gz"', SOURCE)
        self.assertNotIn('if ! tar -xzf "$tmp/extracted/storage.tar.gz"', SOURCE)

    def test_all_untrusted_archive_parsers_are_os_sandboxed(self):
        # The first archive verifier and outer tarfile parser must be isolated,
        # not only the final storage tar extraction.
        self.assertEqual(SOURCE.count("sandbox=(bwrap "), 1)
        self.assertLess(SOURCE.index("sandbox=(bwrap "), SOURCE.index("status BACKUP_ARCHIVE_INTEGRITY PASS"))
        self.assertIn('--ro-bind "$BACKUP_AGE_IDENTITY" "$tmp/age-identity"', SOURCE)
        self.assertIn('env -u BACKUP_AGE_IDENTITY TMPDIR="$tmp" \\\n    "${sandbox[@]}" bash "$tmp/verify_backup_bundle.sh" --decrypted-bundle', SOURCE)
        self.assertNotIn('"${key_sandbox[@]}" bash "$tmp/verify_backup_bundle.sh"', SOURCE)
        self.assertIn('if ! "${key_sandbox[@]}" age -d -i "$tmp/age-identity"', SOURCE)
        self.assertIn('if ! "${sandbox[@]}" python3 - "$tmp/bundle.tar.gz" "$tmp/extracted"', SOURCE)
        self.assertIn('if ! "${sandbox[@]}" python3 - "$tmp/extracted/metadata.txt"', SOURCE)
        self.assertIn('if ! "${sandbox[@]}" python3 "$tmp/parity.py"', SOURCE)
        self.assertIn('if ! parity="$("${sandbox[@]}" python3 "$tmp/parity.py"', SOURCE)
        self.assertNotIn('bash "$repo/scripts/verify_backup_bundle.sh" "$tmp/encrypted.age"', SOURCE)
        self.assertNotIn('if ! age -d -i "$BACKUP_AGE_IDENTITY"', SOURCE)
        self.assertNotIn('if ! python3 - "$tmp/bundle.tar.gz"', SOURCE)
        self.assertNotIn('if ! python3 "$repo/scripts/operations/verify-restored-storage-parity.py"', SOURCE)

    def test_plaintext_archive_verification_never_receives_age_key(self):
        verifier = (SCRIPT.parent.parent / "verify_backup_bundle.sh").read_text(encoding="utf-8")
        self.assertIn('if [[ "${1:-}" == --decrypted-bundle ]]; then', verifier)
        self.assertIn('[[ $# -eq 2 && -z "${BACKUP_AGE_IDENTITY:-}" ]]', verifier)
        self.assertIn('bundle_tar=$BUNDLE_PATH', verifier)
        self.assertIn('python3 - "$bundle_tar" "$WORKDIR"', verifier)
        self.assertIn('if ! "${key_sandbox[@]}" age -d -i "$tmp/age-identity"', SOURCE)
        self.assertLess(SOURCE.index('rm -- "$tmp/age-identity"'),
                        SOURCE.index('bash "$tmp/verify_backup_bundle.sh" --decrypted-bundle'))
        self.assertNotIn('"${key_sandbox[@]}" bash "$tmp/verify_backup_bundle.sh"', SOURCE)
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        subprocess.run(["bash", "-n", str(SCRIPT.parent.parent / "verify_backup_bundle.sh")], check=True)

    def test_plaintext_verifier_rejects_identity_and_invalid_arity_before_io(self):
        verifier = SCRIPT.parent.parent / "verify_backup_bundle.sh"
        env = dict(os.environ)
        env["BACKUP_AGE_IDENTITY"] = "/not-a-real-key"
        forbidden = subprocess.run(
            ["bash", str(verifier), "--decrypted-bundle", "/not-a-real-bundle"],
            env=env, capture_output=True, text=True,
        )
        self.assertEqual(forbidden.returncode, 2)
        self.assertIn("plaintext mode requires", forbidden.stderr)
        env.pop("BACKUP_AGE_IDENTITY", None)
        missing = subprocess.run(
            ["bash", str(verifier), "--decrypted-bundle"],
            env=env, capture_output=True, text=True,
        )
        self.assertEqual(missing.returncode, 2)
        self.assertIn("plaintext mode requires", missing.stderr)

    def test_nonroot_bwrap_mount_preflight_is_fail_closed(self):
        # Source contract only; real Google info user namespace/mount execution
        # is still required before this can be accepted as a restore receipt.
        start = SOURCE.index("GOOGLE_BWRAP_MOUNT_PREFLIGHT")
        first_archive = SOURCE.index("status SFTP_IMPORTED_ENCRYPTED_SHA256 PASS")
        self.assertLess(start, first_archive)
        self.assertIn('if ! "${key_sandbox[@]}" bash -c', SOURCE)
        self.assertIn('if ! "${sandbox[@]}" bash -c', SOURCE)
        self.assertIn('[[ -f "$key" && -r "$key" && -d "$work" && -w "$work" ]]', SOURCE)
        self.assertIn('[[ ! -e "$home/.ssh" && ! -e "$home/.config" ]]', SOURCE)
        self.assertIn('probe="$(mktemp "$work/.bwrap-mount-preflight.XXXXXXXX")"', SOURCE)
        self.assertIn('block GOOGLE_BWRAP_MOUNT_PREFLIGHT', SOURCE)

    def test_disposable_sql_sandbox_never_mounts_age_identity(self):
        # A restored SQL dump executes with a disposable PG superuser. It must
        # not inherit the AGE private key mount used during decryption.
        self.assertIn('key_sandbox=("${sandbox[@]}" --ro-bind "$BACKUP_AGE_IDENTITY" "$tmp/age-identity")', SOURCE)
        self.assertIn('block GOOGLE_BWRAP_KEY_ISOLATION', SOURCE)
        self.assertIn('status GOOGLE_BWRAP_KEY_ISOLATION PASS', SOURCE)
        self.assertIn('rm -- "$tmp/age-identity"', SOURCE)
        self.assertLess(SOURCE.index('rm -- "$tmp/age-identity"'), SOURCE.index('cat >"$tmp/db-phase.sh"'))
        self.assertIn('if ! "${sandbox[@]}" bash "$tmp/db-phase.sh"', SOURCE)
        self.assertNotIn('"${key_sandbox[@]}" bash "$tmp/db-phase.sh"', SOURCE)
        self.assertIn('if ! "${sandbox[@]}" python3 "$tmp/parity.py"', SOURCE)

    def test_safety_properties_kept(self):
        for needle in ("bwrap", "NONROOT_INFO_REQUIRED", "OPERATOR_CONSENT", "PRODUCTION_DATABASE_MODIFIED NO",
                       "status OFFSITE_RCLONE_RETRIEVAL NOT_ATTEMPTED", "SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN",
                       'RESTORE_CANDIDATE_SHA "$candidate_sha"'):
            self.assertIn(needle, SOURCE)
        for prohibited in ("systemctl restart", "artisan migrate", "rclone copy", "ln -sfn"):
            self.assertNotIn(prohibited, SOURCE)


if __name__ == "__main__":
    unittest.main()
