import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller.opencode_free import (
    DEFAULT_MODELS,
    OpenCodeUnavailable,
    configured_models,
    isolated_environment,
    parse_completion,
    probe_zero_cost_route,
    verify_zero_price,
)

PRICE = "[cost]\ninput = 0.0\noutput = 0.0\ncache_read = 0.0\ncache_write = 0.0\n"


def completion(cost=0, reason="stop"):
    return "\n".join([
        json.dumps({"type": "text", "part": {"text": "safe result"}}),
        json.dumps({"type": "step_finish", "part": {"cost": cost, "reason": reason}}),
    ])


class OfficialFreeClientTests(unittest.TestCase):
    def test_accepts_all_four_explicit_zero_prices(self):
        verify_zero_price(PRICE)

    def test_rejects_any_nonzero_price(self):
        for key in ("input", "output", "cache_read", "cache_write"):
            with self.subTest(key=key), self.assertRaises(OpenCodeUnavailable):
                verify_zero_price(PRICE.replace(f"{key} = 0.0", f"{key} = 0.001"))

    def test_rejects_missing_or_boolean_or_malformed_price(self):
        for value in (PRICE.replace("output = 0.0\n", ""), PRICE.replace("input = 0.0", "input = false"), "not toml"):
            with self.subTest(value=value), self.assertRaises(OpenCodeUnavailable):
                verify_zero_price(value)

    def test_accepts_completed_zero_cost_response(self):
        self.assertEqual(parse_completion(completion()), "safe result")

    def test_rejects_paid_unknown_or_incomplete_completion(self):
        for value in (completion(0.01), completion(None), completion(False), completion(reason="length"), ""):
            with self.subTest(value=value), self.assertRaises(OpenCodeUnavailable):
                parse_completion(value)

    def test_rejects_error_even_with_text(self):
        with self.assertRaises(OpenCodeUnavailable):
            parse_completion(completion() + '\n{"type":"error"}')

    def test_probe_retries_transient_non_json_response(self):
        responses = iter([
            {
                "provider": "opencode-client",
                "response": {"choices": [{"message": {"content": "temporary prose"}}]},
            },
            {
                "provider": "opencode-client",
                "response": {"choices": [{"message": {"content": '{"marker":"KMJ_FREE_ROUTE_OK"}'}}]},
            },
        ])
        calls = []

        def fake_complete(messages):
            calls.append(messages)
            return next(responses)

        result = probe_zero_cost_route(fake_complete, max_attempts=3)

        self.assertEqual(result["provider"], "opencode-client")
        self.assertEqual(len(calls), 2)

    def test_probe_fails_closed_after_bounded_invalid_responses(self):
        def fake_complete(_messages):
            return {
                "provider": "opencode-client",
                "response": {"choices": [{"message": {"content": "not json"}}]},
            }

        with self.assertRaisesRegex(OpenCodeUnavailable, "OPENCODE_PROBE_FORMAT_INVALID"):
            probe_zero_cost_route(fake_complete, max_attempts=3)

    def test_client_gets_no_repository_or_provider_credentials(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            "GITHUB_TOKEN": "must-not-propagate",
            "OPENROUTER_API_KEY": "must-not-propagate",
            "STAGING_SSH_PRIVATE_KEY": "must-not-propagate",
        }):
            env = isolated_environment(Path(temporary), DEFAULT_MODELS[0])
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("OPENROUTER_API_KEY", env)
        self.assertNotIn("STAGING_SSH_PRIVATE_KEY", env)
        config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["permission"], {"*": "deny"})
        self.assertEqual(config["small_model"], DEFAULT_MODELS[0])
        self.assertEqual(config["enabled_providers"], ["opencode"])
        self.assertEqual(config["agent"]["build"]["permission"], {"*": "deny"})
        self.assertIn("exactly the requested output format", config["agent"]["build"]["prompt"])


if __name__ == "__main__":
    unittest.main()
