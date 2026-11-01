import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parent / "operations/verify-offsite-restore-witness-20261101.py"
spec = importlib.util.spec_from_file_location("witness", SCRIPT)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

CAND = "dfa55d24b7cc5a0d1e0b0f28832d1f46acc9d031"
REL = "platform-dfa55d24b7cc"
ENC = "fb333fd5" + "0" * 56
SRC = "131f6276" + "1" * 56

SEAL = f"""SOURCE_WITNESS=PASS
SOURCE_LOCAL_SHA256={SRC}
ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS
ENCRYPTED_OFFSITE_BUNDLE=PASS
ENCRYPTED_SHA256={ENC}
ENCRYPTED_BYTES=290397
OFFSITE_TRANSFER=NOT_ATTEMPTED
PRODUCTION_RELEASE=UNCHANGED
PRODUCTION_DB=UNTOUCHED
"""
PUSH = f"""HOSTKEY_PIN=PASS
LOCAL_ENCRYPTED_SHA256={ENC}
REMOTE_CAPABILITY_PROBE=PASS
SFTP_UPLOAD=PASS
REMOTE_COMMIT_NO_CLOBBER=PASS
REMOTE_READBACK_MODE_0600=PASS
REMOTE_READBACK_SHA256=PASS
OFFSITE_PUSH=PASS
OFFSITE_RESTORE=NOT_VERIFIED
PRODUCTION_CHANGED=NO
"""
RESTORE = f"""SFTP_IMPORTED_ENCRYPTED_SHA256=PASS
SFTP_IMPORT_COPY=PASS
OFFSITE_RCLONE_RETRIEVAL=NOT_ATTEMPTED
BACKUP_ARCHIVE_INTEGRITY=PASS
BUNDLE_METADATA_BINDING=PASS
DATABASE_PHASE_OS_SANDBOX=PASS
STORAGE_EXTRACTION_CAPACITY=PASS
STORAGE_EXTRACTION_PARITY_CONTENT_SHA256=PASS
STORAGE_REGULAR_FILES=3
STORAGE_BYTES=61
DISPOSABLE_POSTGRES_RESTORE=PASS
RECOVERED_APP_SCHEMA=PASS
RECOVERED_STORAGE=PASS
POSTGRES_NETWORK_LISTENER=DISABLED
PRODUCTION_DATABASE_MODIFIED=NO
RECOVERED_APP_FUNCTIONAL_QA=NOT_VERIFIED
SMTP_INBOX_DELIVERY=NOT_VERIFIED
OWNER_VISUAL_SIGNOFF=NOT_VERIFIED
MATCHING_PRODUCTION_APPROVAL=NOT_VERIFIED
SAFE_TO_ACTIVATE_PRODUCTION=NOT_PROVEN
GOOGLE_VPS_INDEPENDENT_RESTORE=PASS
OFFSITE_REMOTE_ARCHIVE_RETENTION=NOT_VERIFIED
RESTORE_CANDIDATE_SHA={CAND}
"""


def run(seal=SEAL, push=PUSH, restore=RESTORE, **kw):
    args = dict(candidate=CAND, release=REL, encrypted=ENC, source=SRC, min_files=1)
    args.update(kw)
    return w.verify(seal, push, restore, **args)


class WitnessTest(unittest.TestCase):
    def blocked(self, code, **kw):
        with self.assertRaises(w.Block) as ctx:
            run(**kw)
        self.assertEqual(str(ctx.exception), code)

    def test_genuine_chain_is_partial_pass_without_authority(self):
        result = run()
        self.assertEqual(result["WITNESS"], "PARTIAL_PASS")
        self.assertEqual(result["RELEASE_AUTHORITY"], "NO")
        self.assertEqual(result["PRODUCTION_SWITCH_ALLOWED"], "NO")
        self.assertIn("APP_QA", result["NOT_VERIFIED"])

    def test_target_exists_identical_object_is_accepted_only_via_readback_pass(self):
        run(push=PUSH.replace("REMOTE_COMMIT_NO_CLOBBER=PASS", "REMOTE_COMMIT_NO_CLOBBER=TARGET_EXISTS_OR_FAILED"))
        self.blocked("MISSING_KEY", push=PUSH.replace("REMOTE_READBACK_SHA256=PASS\n", ""))

    def test_forged_or_unbound_values_are_blocked(self):
        self.blocked("ENCRYPTED_SHA_UNBOUND", encrypted="a" * 64)
        self.blocked("ENCRYPTED_SHA_UNBOUND", push=PUSH.replace(ENC, "b" * 64))
        self.blocked("SOURCE_SHA_UNBOUND", source="c" * 64)
        self.blocked("CANDIDATE_UNBOUND", candidate="e" * 40, release="platform-eeeeeeeeeeee")
        self.blocked("RELEASE_CANDIDATE_MISMATCH", release="platform-000000000000")

    def test_duplicates_unknown_keys_and_noise_are_blocked(self):
        self.blocked("DUPLICATE_KEY", restore=RESTORE + "RECOVERED_STORAGE=PASS\n")
        self.blocked("UNKNOWN_KEY", restore=RESTORE + "EXTRA=PASS\n")
        self.blocked("MALFORMED_LINE", restore=RESTORE + "root@host:~# done\n")
        self.blocked("MALFORMED_LINE", push="OFFSITE_PUSH = PASS\n" + PUSH)

    def test_failures_and_overclaims_are_blocked(self):
        self.blocked("BAD_VALUE", restore=RESTORE.replace("RECOVERED_STORAGE=PASS", "RECOVERED_STORAGE=FAIL"))
        self.blocked("BAD_VALUE", push=PUSH.replace("REMOTE_READBACK_MODE_0600=PASS", "REMOTE_READBACK_MODE_0600=NOT_0600"))
        self.blocked("BAD_VALUE", restore=RESTORE.replace("OWNER_VISUAL_SIGNOFF=NOT_VERIFIED", "OWNER_VISUAL_SIGNOFF=PASS"))
        self.blocked("BAD_VALUE", restore=RESTORE.replace("SAFE_TO_ACTIVATE_PRODUCTION=NOT_PROVEN", "SAFE_TO_ACTIVATE_PRODUCTION=YES"))
        self.blocked("BAD_VALUE", push=PUSH.replace("OFFSITE_RESTORE=NOT_VERIFIED", "OFFSITE_RESTORE=PASS"))
        self.blocked("BAD_VALUE", seal=SEAL.replace("OFFSITE_TRANSFER=NOT_ATTEMPTED", "OFFSITE_TRANSFER=PASS"))

    def test_upload_coverage_floor(self):
        self.blocked("UPLOAD_COVERAGE_BELOW_EXPECTED", min_files=4)
        self.assertEqual(run(min_files=3)["RESTORED_REGULAR_FILES"], "3")

    def test_schema_less_text_cannot_pass(self):
        self.blocked("MISSING_KEY", restore="GOOGLE_VPS_INDEPENDENT_RESTORE=PASS\n")

    def test_cli_digest_binding_and_file_rules(self):
        with tempfile.TemporaryDirectory() as d:
            files = {}
            for name, text in (("seal", SEAL), ("push", PUSH), ("restore", RESTORE)):
                path = Path(d, name)
                path.write_text(text)
                files[name] = f"{path}:{hashlib.sha256(text.encode()).hexdigest()}"
            base = ["--candidate-sha", CAND, "--expected-release", REL, "--encrypted-sha256", ENC,
                    "--source-local-sha256", SRC, "--min-storage-files", "1"]

            def cli(**override):
                f = {**files, **override}
                return subprocess.run([sys.executable, "-I", str(SCRIPT), *base, "--seal", f["seal"],
                                       "--push", f["push"], "--restore", f["restore"]],
                                      capture_output=True, text=True)
            ok = cli()
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertIn("WITNESS=PARTIAL_PASS", ok.stdout)
            Path(d, "restore").write_text(RESTORE + "\n# edited\n")
            tampered = cli()
            self.assertEqual(tampered.returncode, 2)
            self.assertIn("RECEIPT_DIGEST_MISMATCH", tampered.stdout)
            link = Path(d, "link"); link.symlink_to(Path(d, "push"))
            bad = cli(push=f"{link}:{hashlib.sha256(PUSH.encode()).hexdigest()}")
            self.assertIn("RECEIPT_FILE", bad.stdout)
            usage = subprocess.run([sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True)
            self.assertIn("BLOCKED USAGE", usage.stdout)

    def test_noncanonical_whitespace_never_enters_receipt_chain(self):
        for altered in (
            SEAL.replace("SOURCE_WITNESS=PASS", " SOURCE_WITNESS=PASS"),
            SEAL.replace("SOURCE_WITNESS=PASS", "SOURCE_WITNESS=PASS "),
            SEAL.replace("SOURCE_WITNESS=PASS", "\tSOURCE_WITNESS=PASS"),
        ):
            self.blocked("NONCANONICAL_LINE", seal=altered)

    def test_nonregular_receipt_fifo_rejected_without_read_or_hang(self):
        with tempfile.TemporaryDirectory() as d:
            fifo = Path(d, "incoming")
            os.mkfifo(fifo)
            with self.assertRaises(w.Block) as error:
                w.load(str(fifo) + ":" + hashlib.sha256(PUSH.encode()).hexdigest())
            self.assertEqual(str(error.exception), "RECEIPT_FILE")

    def test_short_regular_file_read_rejects_digest_matching_prefix(self):
        # Simulate a short os.read on an otherwise stable regular file.
        # The prefix digest is valid, but unexamined trailing bytes must block.
        with tempfile.TemporaryDirectory() as d:
            receipt = Path(d, "push")
            prefix = PUSH.encode("ascii")
            receipt.write_bytes(prefix + b"EXTRA=UNTRUSTED\\n")
            original_read = os.read
            with patch.object(w.os, "read", side_effect=lambda fd, amount: original_read(fd, len(prefix))):
                with self.assertRaises(w.Block) as error:
                    w.load(str(receipt) + ":" + hashlib.sha256(prefix).hexdigest())
            self.assertEqual(str(error.exception), "RECEIPT_FILE_CHANGED")

    def test_descriptor_read_ignores_raced_symlink_replacement(self):
        # Swap the pathname only AFTER the safe fd is open. The verified
        # bytes must come from the originally opened inode, not the link.
        with tempfile.TemporaryDirectory() as d:
            original = Path(d, "push")
            original.write_text(PUSH)
            secret = Path(d, "secret")
            secret.write_text("SHOULD_NOT_BE_READ")
            renamed = Path(d, "previous")
            expected = hashlib.sha256(PUSH.encode()).hexdigest()
            real_read = os.read
            swapped = False

            def swap_just_before_read(fd, amount):
                nonlocal swapped
                if not swapped:
                    original.rename(renamed)
                    original.symlink_to(secret)
                    swapped = True
                return real_read(fd, amount)

            with patch.object(w.os, "read", side_effect=swap_just_before_read):
                # Even the *original* opened inode changed ctime when renamed.
                # The verifier deliberately fails closed instead of accepting
                # a receipt whose pathname or inode metadata changed midread.
                with self.assertRaises(w.Block) as error:
                    w.load(str(original) + ":" + expected)
            self.assertTrue(swapped)
            self.assertEqual(str(error.exception), "RECEIPT_FILE_CHANGED")
            self.assertTrue(original.is_symlink())

    def test_direct_symlink_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            original = Path(d, "real")
            original.write_text(PUSH)
            link = Path(d, "link")
            link.symlink_to(original)
            with self.assertRaises(w.Block) as error:
                w.load(str(link) + ":" + hashlib.sha256(PUSH.encode()).hexdigest())
            self.assertEqual(str(error.exception), "RECEIPT_FILE")

    def test_source_is_offline_and_readonly(self):
        body = SCRIPT.read_text().split('"""', 2)[2]
        for forbidden in ("subprocess", "socket", "os.system", "urllib", "write_text", "write_bytes", "unlink", "chmod"):
            self.assertNotIn(forbidden, body, forbidden)


if __name__ == "__main__":
    unittest.main()
