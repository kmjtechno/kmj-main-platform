#!/usr/bin/env python3
"""Source-only and pure-function tests for candidate dotenv staging. No host operations."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/operations/stage-codebridge-agent-production-env-20261024.py"
spec = importlib.util.spec_from_file_location("candidate_env_stage", FILE)
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
SOURCE = FILE.read_text("utf-8")


class CandidateEnvContracts(unittest.TestCase):
    def test_append_public_agent_key_preserving_existing_env_and_secret(self):
        source = b"APP_KEY=private-test-key\nCODEBRIDGE_GATEWAY_URL=http://127.0.0.1:18787\n"
        result = stage.pin_public_origin(source)
        self.assertEqual(result, source + b"CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com\n")
        self.assertEqual(result.count(b"APP_KEY="), 1)

    def test_no_trailing_newline_and_idempotent(self):
        raw = b"APP_ENV=production"
        staged = stage.pin_public_origin(raw)
        self.assertEqual(staged, raw + b"\nCODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com\n")
        self.assertEqual(stage.pin_public_origin(staged), staged)

    def test_conflicting_public_origin_rejected(self):
        for value in [
            b"CODEBRIDGE_AGENT_PUBLIC_URL=http://127.0.0.1:18787\n",
            b"CODEBRIDGE_AGENT_PUBLIC_URL=https://evil.invalid\n",
            b"CODEBRIDGE_AGENT_PUBLIC_URL='https://kmjtechno.com'\n",
        ]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "PUBLIC_AGENT_ORIGIN_CONFLICT"):
                    stage.pin_public_origin(value)

    def test_duplicate_public_origin_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "DUPLICATE_PUBLIC_AGENT_ORIGIN"):
            stage.pin_public_origin(b"CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com\n"
                                    b"CODEBRIDGE_AGENT_PUBLIC_URL=https://kmjtechno.com\n")

    def test_unknown_binary_and_newline_rejected(self):
        for data in [b"APP_ENV=\xff\n", b"APP_KEY=test\r\n", b"KEY=x\x00y"]:
            with self.subTest(data=data):
                with self.assertRaises(RuntimeError):
                    stage.pin_public_origin(data)

    def test_release_and_backup_exactly_pinned(self):
        self.assertEqual(stage.SHA, "b1d672bbc83a51ca3f8271435692825072444c8e")
        self.assertEqual(stage.OLD, "platform-8070dad72c55")
        self.assertEqual(stage.CANDIDATE.name, "platform-b1d672bbc83a")
        self.assertEqual(stage.WITNESS.name, "pre-deploy-b1d672bbc83a.json")
        for token in ["BACKUP_WITNESS_IDENTITY", "BACKUP_WITNESS_DIGEST_MISMATCH",
                      "CANDIDATE_SHA_MISMATCH", "CANDIDATE_DIRTY",
                      "ENV_SOURCE_LINK_OR_CANDIDATE_PRESENT",
                      "CANDIDATE_ALREADY_CACHED"]:
            self.assertIn(token, SOURCE)

    def test_no_live_mutation_and_no_bypass(self):
        for unsafe in ["systemctl start", "systemctl restart", "systemctl reload",
                       "artisan migrate", "git reset", "os.replace(", "APPROVAL.write",
                       "CURRENT.unlink", "LIVE_ENV_SOURCE.print", "print(source_bytes)",
                       "approval.json", "sudo -S", "curl | bash"]:
            self.assertNotIn(unsafe, SOURCE)
        self.assertIn("os.O_EXCL | os.O_NOFOLLOW", SOURCE)
        self.assertIn("os.fchmod(fd, metadata.st_mode & 0o660)", SOURCE)
        self.assertIn("PRODUCTION_ACTIVATION=NOT_ATTEMPTED", SOURCE)
        self.assertIn("LIVE_ENV=UNCHANGED", SOURCE)


if __name__ == "__main__":
    unittest.main()
