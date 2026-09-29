import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.free_provider_health import atomic_write, build_snapshot


class FreeProviderHealthTests(unittest.TestCase):
    def test_healthy_when_verified_zero_route_is_reachable(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = build_snapshot({
                "configured_providers": ["groq"],
                "reachable_providers": ["groq"],
                "provider_errors": {},
                "eligible_verified_zero": 2,
                "eligible_confidential_verified_zero": 0,
                "rejected_unknown_or_paid": 3,
            })

        self.assertEqual("healthy", snapshot["status"])
        self.assertEqual(2, snapshot["eligible_verified_zero"])
        self.assertEqual("PROHIBITED", snapshot["paid_fallback"])
        self.assertFalse(snapshot["unknown_cost_is_free"])

    def test_dormant_when_no_route_or_client_is_available(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = build_snapshot({
                "configured_providers": ["9router"],
                "reachable_providers": [],
                "provider_errors": {"9router": "ConnectError"},
                "eligible_verified_zero": 0,
            })

        self.assertEqual("dormant", snapshot["status"])
        self.assertFalse(snapshot["opencode_client_ready"])

    def test_degraded_when_no_key_opencode_client_is_ready(self):
        with tempfile.NamedTemporaryFile() as binary, patch.dict(
            os.environ,
            {
                "KMJ_OPENCODE_FREE_ENABLED": "true",
                "KMJ_OPENCODE_BINARY": binary.name,
            },
            clear=True,
        ):
            snapshot = build_snapshot({
                "configured_providers": ["9router"],
                "reachable_providers": [],
                "provider_errors": {"9router": "ConnectError"},
                "eligible_verified_zero": 0,
            })

        self.assertEqual("degraded", snapshot["status"])
        self.assertTrue(snapshot["opencode_client_ready"])

    def test_atomic_write_replaces_target_with_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "health.json"
            atomic_write(target, {"status": "healthy"})
            self.assertEqual({"status": "healthy"}, json.loads(target.read_text()))
