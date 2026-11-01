import importlib.util
import os
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
exit_255=YES
journal_scope=EXACT_INVOCATION
journal_failure_class=SSH_AUTH_KEY_REJECTED
journal_auth_subclass=PUBLICKEY_AUTH_DENIED
raw_values_emitted=NO
A2_DIAGNOSTIC=READ_ONLY_COMPLETE
"""
A2B = """schema=kmj.a2.unit-identity.readonly.v1
executable_reads_sftp_config=NO
authorized_fingerprint_match=YES
mutations=NONE
raw_values_emitted=NO
"""
TRACE_SINGLE = "effective_identity=SINGLE_CANDIDATE_UNPROVEN\nauthorized_overlap=NO\n"
TRACE_AMBIG = "effective_identity=AMBIGUOUS_OR_UNPROVEN\nauthorized_overlap=UNKNOWN_NO_OWNER_ALLOWLIST\n"
WITNESS = "restore_verified=PASS\nrestore_scope=DB_AND_ALL_UPLOADS\nsource_local_sha256=" + "a" * 64 + "\n"


class PlannerTest(unittest.TestCase):
    def decide(self, *docs):
        return planner.plan(list(docs))

    def test_never_allows_apply_or_mutation(self):
        for docs in ([A2, A2B, TRACE_SINGLE, WITNESS], [A2], ["garbage"], []):
            result = self.decide(*docs)
            self.assertEqual(result["APPLY_ALLOWED"], "NO")
            self.assertEqual(result["MUTATIONS"], "NONE")

    def test_missing_or_malformed_evidence_is_blocked(self):
        self.assertEqual(self.decide()["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide("not a receipt")["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide(A2B)["DECISION"], "BLOCKED_EVIDENCE")
        self.assertEqual(self.decide(A2)["DECISION"], "BLOCKED_EVIDENCE")

    def test_conflicting_duplicate_values_are_rejected(self):
        self.assertEqual(self.decide(A2, A2B, "exit_255=NO\n")["DECISION"], "BLOCKED_EVIDENCE")

    def test_paths_keys_and_hosts_are_rejected(self):
        for bad in ("candidate=/root/.ssh/id\n", "x=-----BEGIN OPENSSH PRIVATE KEY-----\n", "host=a@b\n", "p=../x\n"):
            self.assertEqual(self.decide(A2, A2B, bad)["DECISION"], "BLOCKED_EVIDENCE", bad)

    def test_unknown_schema_is_rejected(self):
        self.assertEqual(self.decide(A2.replace("v1", "v9"), A2B)["DECISION"], "BLOCKED_EVIDENCE")

    def test_non_auth_failure_is_routed_away(self):
        for field, value in (("journal_auth_subclass", "OTHER"), ("exit_255", "NOT_PROVEN"),
                             ("journal_scope", "UNAVAILABLE")):
            doc = A2.replace(next(l for l in A2.splitlines() if l.startswith(field)), f"{field}={value}")
            self.assertEqual(self.decide(doc, A2B, TRACE_SINGLE, WITNESS)["DECISION"], "NOT_AUTH_FAILURE")

    def test_authorized_identity_that_is_read_by_unit_is_inconsistent(self):
        doc = A2B.replace("executable_reads_sftp_config=NO", "executable_reads_sftp_config=YES")
        self.assertEqual(self.decide(A2, doc, TRACE_SINGLE, WITNESS)["DECISION"], "INVESTIGATE_INCONSISTENT")

    def test_waits_for_restore_witness_before_any_plan(self):
        for trace, planned in ((TRACE_SINGLE, "REPOINT_IDENTITY_REVIEW"), (TRACE_AMBIG, "RETIRE_LEGACY_REVIEW")):
            result = self.decide(A2, A2B.replace("authorized_fingerprint_match=YES", "authorized_fingerprint_match=NO"), trace)
            self.assertEqual(result["DECISION"], "WAIT_FOR_RESTORE_WITNESS")
            self.assertEqual(result["PLANNED_AFTER_WITNESS"], planned)

    def test_plans_after_complete_witness(self):
        b = A2B.replace("authorized_fingerprint_match=YES", "authorized_fingerprint_match=NO")
        self.assertEqual(self.decide(A2, b, TRACE_SINGLE, WITNESS)["DECISION"], "REPOINT_IDENTITY_REVIEW")
        self.assertEqual(self.decide(A2, b, TRACE_AMBIG, WITNESS)["DECISION"], "RETIRE_LEGACY_REVIEW")
        partial = WITNESS.replace("DB_AND_ALL_UPLOADS", "DB_ONLY")
        self.assertEqual(self.decide(A2, b, TRACE_AMBIG, partial)["DECISION"], "WAIT_FOR_RESTORE_WITNESS")
        weak = WITNESS.replace("a" * 64, "abc")
        self.assertEqual(self.decide(A2, b, TRACE_AMBIG, weak)["DECISION"], "WAIT_FOR_RESTORE_WITNESS")

    def test_identity_is_never_claimed_proven(self):
        b = A2B.replace("authorized_fingerprint_match=YES", "authorized_fingerprint_match=NO")
        self.assertEqual(self.decide(A2, b, TRACE_SINGLE, WITNESS)["IDENTITY_SOURCE"], "UNPROVEN")

    def test_cli_rejects_symlink_oversize_and_usage(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d, "r"); real.write_text(A2)
            link = Path(d, "l"); link.symlink_to(real)
            big = Path(d, "b"); big.write_text("a=b\n" * 5000)
            for args, code in (([], "PLAN=BLOCKED_USAGE"), ([str(link)], "PLAN=BLOCKED_INPUT_FILE"),
                               ([str(big)], "PLAN=BLOCKED_INPUT_FILE")):
                run = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)
                self.assertIn(code, run.stdout)

    def test_source_is_offline_and_readonly(self):
        source = SCRIPT.read_text()
        for forbidden in ("subprocess", "socket", "os.system", "urllib", "write_text", "open(", "unlink", "chmod", "systemctl", "ssh-keygen"):
            self.assertNotIn(forbidden, source.split('"""', 2)[2], forbidden)


if __name__ == "__main__":
    unittest.main()
