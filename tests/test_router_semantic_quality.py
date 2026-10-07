import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from controller.model_router import FreeCloudRouter


class SemanticQualityRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "router.sqlite"
        self.env = patch.dict(os.environ, {"KMJ_ROUTER_STATE_DB": str(self.state)})
        self.env.start()
        self.router = FreeCloudRouter()
        self.models = [
            {
                "id": "model-a", "owned_by": "owner", "_kmj_provider": "9router",
                "_kmj_allow_confidential": True, "_kmj_provider_priority": 0,
            },
            {
                "id": "model-b", "owned_by": "owner", "_kmj_provider": "9router",
                "_kmj_allow_confidential": True, "_kmj_provider_priority": 0,
            },
        ]
        self.eligible = patch.object(self.router, "_eligible", return_value=(True, "verified"))
        self.eligible.start()

    def tearDown(self):
        self.eligible.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_tested_failure_demotes_model_below_untested_peer(self):
        self.router.semantic_quality(
            provider="9router", model_id="model-a", passed=False,
            evidence_id="workflow:1:test-hash",
        )
        ranked = self.router.rank(self.models, "coding", "confidential")
        self.assertEqual([r.model_id for r in ranked], ["model-b", "model-a"])

    def test_tested_success_promotes_model_above_untested_peer(self):
        self.router.semantic_quality(
            provider="9router", model_id="model-b", passed=True,
            evidence_id="workflow:1:test-hash",
        )
        ranked = self.router.rank(self.models, "coding", "confidential")
        self.assertEqual([r.model_id for r in ranked], ["model-b", "model-a"])

    def test_same_evidence_is_exactly_once_and_counts_are_bounded(self):
        for _ in range(3):
            self.router.semantic_quality(
                provider="9router", model_id="model-a", passed=False,
                evidence_id="same-evidence",
            )
        key = self.router._quality_key("9router", "model-a")
        self.assertEqual(self.router.semantic_quality()[key][:2], (0, 1))
        for index in range(20):
            self.router.semantic_quality(
                provider="9router", model_id="model-a", passed=False,
                evidence_id=f"failure-{index}",
            )
        self.assertEqual(self.router.semantic_quality()[key][1], 8)

    def test_privacy_filter_remains_authoritative_over_quality(self):
        self.router.semantic_quality(
            provider="9router", model_id="model-a", passed=True,
            evidence_id="pass",
        )
        models = [dict(self.models[0], _kmj_allow_confidential=False), self.models[1]]
        ranked = self.router.rank(models, "coding", "confidential")
        self.assertEqual([r.model_id for r in ranked], ["model-b"])


if __name__ == "__main__":
    unittest.main()
