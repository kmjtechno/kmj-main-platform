from __future__ import annotations

import io
import json
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "staging" / "verify-monitor.py"
ORIGIN = "https://staging.kmjtechno.com"


class FakeResponse(io.BytesIO):
    def __init__(self, payload: dict, url: str):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.status = 200
        self._url = url

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class StagingMonitorContractTests(unittest.TestCase):
    def test_verifier_accepts_delivery_control_monitor_component(self):
        def fake_urlopen(request, timeout=20):
            url = request.full_url
            if url == ORIGIN + "/info":
                return FakeResponse(
                    {"component": "info-control", "props": {"pollIntervalMs": 5000}},
                    url,
                )
            if url == ORIGIN + "/info/status":
                return FakeResponse(
                    {
                        "status": "healthy",
                        "runtime": {"application": True, "database": True},
                        "deployment": {"deployed_sha": "d" * 40},
                    },
                    url,
                )
            raise AssertionError(f"unexpected URL: {url}")

        with (
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
            patch.object(sys, "argv", [str(SCRIPT)]),
        ):
            runpy.run_path(str(SCRIPT), run_name="__main__")


if __name__ == "__main__":
    unittest.main()
