"""Real A2/A2b/A2c receipts and adversarial spoofed restore evidence."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "operations/plan-offsite-transport-reconcile-20261101.py"
spec = importlib.util.spec_from_file_location("planner", SCRIPT)
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

A2 = """schema=kmj.a2.ssh255.readonly.v1
unit=kmj-elite-offsite-backup.service
unit_load=loaded
exit_255=YES
systemd_user=ROOT
execstart_reference=REFERENCE_ONLY
execstart_hash_attested=NO
journal_scope=EXACT_INVOCATION
journal_failure_class=SSH_AUTH_KEY_REJECTED
journal_auth_subclass=PUBLICKEY_AUTH_DENIED
sftp_config=PRIVATE_VALID
sftp_identity=PRIVATE
hostkey_pin=PIN_FORMAT_VALID
backup_created=NOT_VERIFIED
restore_verified=NO
production_changed=NO_THIS_SCRIPT_IS_READ_ONLY
raw_values_emitted=NO
A2_DIAGNOSTIC=READ_ONLY_COMPLETE
"""
A2B = """schema=kmj.a2.unit-identity.readonly.v1
unit=kmj-elite-offsite-backup.service
unit_loaded=YES
dropins_present=NO
single_execstart=YES
executable_protected=YES
executable_sha256=d66fd2c2cc33c53c1d0a82f1c259640ee642b666feb2c4aaee6cf887dfe98848
executable_reads_sftp_config=NO
executable_embeds_other_identity=NO
config_identity_present=YES
config_identity_protected=YES
config_identity_fingerprint=SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk
authorized_fingerprint_match=UNKNOWN_NO_OWNER_ALLOWLIST
service_identity_source=NOT_PROVEN
local_reference_hint=UNVERIFIED
repair_precondition_met=NO
remote_authorization_witnessed=NO
backup_created=NOT_VERIFIED
restore_verified=NO
mutations=NONE
raw_values_emitted=NO
A2B_COMPARE=READ_ONLY_COMPLETE
"""
A2C = """schema=kmj.a2c.effective-identity.readonly.v1
unit=kmj-elite-offsite-backup.service
unit_user=ROOT
dropins_present=NO
executable=FILE
tools_referenced=rsync,ssh
referenced_paths_scanned=6
unit_home_resolved=YES
candidate_files=1
candidate_0=id=2e7968cdfc43 role=PRIVATE_KEY kind=FILE keys=- fps=SHA256:l5bMMD8ncbEFsjr8ulJHgvPxU6dPT8Fuu5gij46duv8
candidate_fingerprints=SHA256:l5bMMD8ncbEFsjr8ulJHgvPxU6dPT8Fuu5gij46duv8
authorized_overlap=UNKNOWN_NO_OWNER_ALLOWLIST
effective_identity=SINGLE_CANDIDATE_UNPROVEN
remote_auth_witnessed=NO
repair_allowed=NO
backup_created=NOT_VERIFIED
restore_verified=NO
mutations=NONE
raw_values_emitted=NO
A2C_TRACE=READ_ONLY_COMPLETE
"""
FAKE_WITNESS = (
    "restore_verified=PASS\nrestore_scope=DB_AND_ALL_UPLOADS\n"
    + "source_local_sha256=" + "a" * 64 + "\n"
)


class PlannerTest(unittest.TestCase):
    def decide(self, *docs):
        return planner.plan(list(docs))

    def test_real_owner_receipts_are_valid_separate_diagnostics(self):
        self.assertEqual(planner.parse(A2)["restore_verified"], "NO")
        self.assertEqual(planner.parse(A2B)["restore_verified"], "NO")
        self.assertEqual(planner.parse(A2C)["candidate_files"], "1")
        result = self.decide(A2, A2B, A2C)
        self.assertEqual(result["DECISION"], "WAIT_FOR_RESTORE_WITNESS")
        self.assertEqual(result["RESTORE_PROVENANCE"], "UNVERIFIED")
        self.assertEqual(result["IDENTITY_SOURCE"], "UNPROVEN")

    def test_never_allows_apply_or_mutation(self):
        for docs in ([A2, A2B, A2C], [A2], [FAKE_WITNESS], []):
            result = self.decide(*docs)
            self.assertEqual(result["APPLY_ALLOWED"], "NO")
            self.assertEqual(result["MUTATIONS"], "NONE")

    def test_missing_or_malformed_evidence_is_blocked(self):
        self.assertEqual(self.decide()["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide("not a receipt")["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide(A2)["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide(A2B)["DECISION"], "BLOCKED_EVIDENCE")

    def test_fake_or_unbound_restore_pass_never_unlocks_review(self):
        for fake in (
            FAKE_WITNESS,
            "schema=kmj.a2.restore-witness.verified.v1\n" + FAKE_WITNESS,
            "schema=kmj.a2.ssh255.readonly.v1\n" + FAKE_WITNESS,
            "restore_verified=PASS\n",
        ):
            self.assertEqual(self.decide(A2, A2B, fake)["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide(A2, A2B)["DECISION"], "WAIT_FOR_RESTORE_WITNESS")

    def test_real_a2b_no_vs_forged_witness_pass_is_rejected(self):
        self.assertEqual(self.decide(A2, A2B, FAKE_WITNESS)["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide(A2, A2B, A2B.replace(
            "restore_verified=NO", "restore_verified=PASS"))["DECISION"], "BLOCKED_EVIDENCE")

    def test_schema_less_or_duplicate_schema_is_not_trusted(self):
        for extra in (
            "executable_reads_sftp_config=YES\n",
            A2B,
            A2C.replace("schema=kmj.a2c.effective-identity.readonly.v1", ""),
            A2B.replace("schema=kmj.a2.unit-identity.readonly.v1",
                        "schema=kmj.a2.unit-identity.readonly.v9"),
        ):
            self.assertEqual(self.decide(A2, A2B, extra)["DECISION"], "BLOCKED_EVIDENCE")

    def test_unknown_field_duplicate_and_raw_secret_rejected(self):
        for bad in (
            A2 + "new_key=YES\n",
            A2 + "exit_255=YES\n",
            A2 + "candidate=/root/.ssh/private\n",
            A2 + "sshkey=-----BEGIN OPENSSH PRIVATE KEY-----\n",
            A2 + "host=foo@bar\n",
            A2.replace("unit=kmj-elite-offsite-backup.service",
                       "unit=other.service"),
            A2.replace("raw_values_emitted=NO", "raw_values_emitted=YES"),
        ):
            self.assertEqual(self.decide(bad, A2B)["DECISION"], "BLOCKED_EVIDENCE")

    def test_non_auth_failure_is_routed_away(self):
        for field, value in (
            ("journal_auth_subclass", "OTHER"),
            ("exit_255", "NOT_PROVEN"),
            ("journal_scope", "UNAVAILABLE"),
        ):
            doc = A2.replace(
                next(l for l in A2.splitlines() if l.startswith(field + "=")),
                f"{field}={value}"
            )
            self.assertEqual(self.decide(doc, A2B)["DECISION"], "NOT_AUTH_FAILURE")

    def test_inconsistent_authorized_config_gets_no_repair(self):
        altered = A2B.replace("executable_reads_sftp_config=NO",
                              "executable_reads_sftp_config=YES").replace(
            "authorized_fingerprint_match=UNKNOWN_NO_OWNER_ALLOWLIST",
            "authorized_fingerprint_match=YES")
        self.assertEqual(self.decide(A2, altered)["DECISION"], "INVESTIGATE_INCONSISTENT")

    def test_candidate_fingerprint_never_proves_offered_remote_key(self):
        single = A2C.replace("authorized_overlap=UNKNOWN_NO_OWNER_ALLOWLIST",
                             "authorized_overlap=NO")
        result = self.decide(A2, A2B, single)
        self.assertEqual(result["DECISION"], "WAIT_FOR_RESTORE_WITNESS")
        self.assertEqual(result["PLANNED_AFTER_WITNESS"], "RETIRE_LEGACY_REVIEW")
        self.assertNotEqual(result["APPLY_ALLOWED"], "YES")

    def test_missing_safety_markers_or_mutation_must_block(self):
        for bad in (
            A2B.replace("A2B_COMPARE=READ_ONLY_COMPLETE", ""),
            A2B.replace("mutations=NONE", "mutations=CHANGED"),
            A2B.replace("remote_authorization_witnessed=NO",
                        "remote_authorization_witnessed=YES"),
            A2B.replace("repair_precondition_met=NO", "repair_precondition_met=YES"),
        ):
            self.assertEqual(self.decide(A2, bad)["DECISION"], "BLOCKED_EVIDENCE")

    def test_cli_refuses_symlink_oversize_and_usage(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d, "r"); real.write_text(A2)
            link = Path(d, "l"); link.symlink_to(real)
            big = Path(d, "b"); big.write_text("a=b\n" * 5000)
            for args, msg in (
                ([], "PLAN=BLOCKED_USAGE"),
                ([str(link)], "PLAN=BLOCKED_INPUT_FILE"),
                ([str(big)], "PLAN=BLOCKED_INPUT_FILE"),
            ):
                run = subprocess.run(
                    [sys.executable, "-I", str(SCRIPT), *args],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                self.assertIn(msg, run.stdout)

    def test_source_is_offline_and_readonly(self):
        source = SCRIPT.read_text()
        for forbidden in ("import subprocess", "socket.", "os.system",
                          "urllib", "write_text(", "unlink(", "chmod(",
                          "systemctl ", "ssh-keygen "):
            self.assertNotIn(forbidden, source.split('"""', 2)[2], forbidden)


if __name__ == "__main__":
    unittest.main()
