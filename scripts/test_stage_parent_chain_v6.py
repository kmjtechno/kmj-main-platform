"""Offline negative tests for fail-closed staging parent-chain V6 evidence."""
import importlib.util
import os
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).parent / "operations/audit-stage-parent-chain-v6.py"
spec = importlib.util.spec_from_file_location("parent_v6", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ParentChainV6(unittest.TestCase):
    def test_stage_owned_parent_is_renameable_even_when_child_root_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "stage"
            shared = home / "shared"
            shared.mkdir(parents=True)
            home.chmod(0o755)
            shared.chmod(0o755)
            result = module.collect_chain(home, shared)
            self.assertEqual(result["parent_rename_risk"], "YES")
            self.assertFalse(result["staging_switch_authorized"])
            self.assertFalse(result["backup_restore_verified"])
            self.assertFalse(result["owner_release_approved"])
            self.assertEqual(result["status"], "BLOCKED_PARENT_CHAIN_AND_RELEASE_GATES")
            self.assertEqual(result["parent_mode"], "0755")

    def test_symlink_parent_and_child_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = base / "real"
            (actual / "shared").mkdir(parents=True)
            link = base / "link"
            link.symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(module.UnsafeEvidence, "UNTRUSTED_DIRECTORY_CHAIN"):
                module.collect_chain(link, link / "shared")
            (actual / "other").symlink_to(actual / "shared", target_is_directory=True)
            with self.assertRaisesRegex(module.UnsafeEvidence, "UNTRUSTED_DIRECTORY_CHAIN"):
                module.collect_chain(actual, actual / "other")

    def test_unknown_acl_does_not_become_absent(self):
        with patch.object(module.os, "getxattr", side_effect=OSError(13, "denied")):
            self.assertEqual(module.acl_status(Path("/not-read")), "UNKNOWN")

    def test_blocked_evidence_receipt_never_exits_success(self):
        from unittest.mock import MagicMock

        stage = MagicMock()
        stage.is_symlink.return_value = True
        stage.resolve.return_value = (
            Path("/home/kmjstage/releases") / module.STAGE_SHA / "apps/platform"
        )
        prod = MagicMock()
        prod.is_symlink.return_value = True
        prod.resolve.return_value = (
            Path("/home/kmjprod/releases") / module.PROD_RELEASE
        )
        with (
            patch.object(module.os, "geteuid", return_value=0),
            patch.object(module.socket, "gethostname", return_value="KMJ-elite"),
            patch.object(module, "STAGE", stage),
            patch.object(module, "PROD", prod),
            patch.object(module, "directory"),
            patch.object(module, "collect_chain", return_value={
                "status": "BLOCKED_PARENT_CHAIN_AND_RELEASE_GATES",
                "staging_switch_authorized": False,
                "production_activation_authorized": False,
            }),
            patch.object(module, "write_receipt") as writer,
            patch("builtins.print"),
        ):
            self.assertEqual(module.main(), 2)
            writer.assert_called_once()
            evidence = writer.call_args.args[0]
            self.assertEqual(evidence["live_pointer_identity"], "MATCHED_OLD_BASELINE")
            self.assertFalse(evidence["staging_switch_authorized"])

    def test_group_or_world_writable_qa_cannot_hold_root_receipt(self):
        for mode in (0o775, 0o757, 0o777):
            with self.subTest(mode=oct(mode)), tempfile.TemporaryDirectory() as tmp:
                qa = Path(tmp) / "qa"
                qa.mkdir(mode=0o700)
                qa.chmod(mode)
                with patch.object(module, "QA", qa):
                    with self.assertRaisesRegex(module.UnsafeEvidence, "UNTRUSTED_RECEIPT_DIRECTORY"):
                        module.write_receipt({"status": "BLOCKED"})
                self.assertFalse((qa / module.RECEIPT).exists())

    def test_symlink_qa_directory_rejected_before_receipt_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            actual = Path(tmp) / "real"
            actual.mkdir()
            qa = Path(tmp) / "qa"
            qa.symlink_to(actual, target_is_directory=True)
            with patch.object(module, "QA", qa):
                with self.assertRaisesRegex(module.UnsafeEvidence, "UNTRUSTED_DIRECTORY_CHAIN"):
                    module.write_receipt({"status": "BLOCKED"})
            self.assertFalse((actual / module.RECEIPT).exists())

    def test_staging_owned_qa_is_rejected_even_if_not_group_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            qa = Path(tmp) / "qa"
            qa.mkdir(mode=0o700)
            qa.chmod(0o700)
            with patch.object(module, "QA", qa):
                with patch.object(module.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=os.getuid())):
                    with self.assertRaisesRegex(module.UnsafeEvidence, "UNTRUSTED_RECEIPT_DIRECTORY"):
                        module.write_receipt({"status": "BLOCKED"})
            self.assertFalse((qa / module.RECEIPT).exists())

    def test_receipt_source_never_mutates_customer_tree_or_authorizes(self):
        source = SOURCE.read_text()
        self.assertIn("os.O_EXCL | os.O_NOFOLLOW", source)
        self.assertIn("os.fchmod(stream.fileno(), 0o640)", source)
        self.assertIn('"production_activation_authorized": False', source)
        self.assertIn('"staging_switch_authorized": False', source)
        self.assertNotIn("shutil.move", source)
        self.assertNotIn("os.rename(", source)


if __name__ == "__main__":
    unittest.main()
