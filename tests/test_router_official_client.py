import os
import unittest
from unittest.mock import AsyncMock, patch

from controller.model_router import (
    FreeCloudRouter,
    NoFreeRouteAvailable,
    ProviderEndpoint,
)
from controller.opencode_free import OpenCodeUnavailable


class RouterOfficialClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloudflare_provider_requires_token_and_account_and_is_public_only(self):
        with patch.dict(
            os.environ,
            {
                "CLOUDFLARE_API_TOKEN": "test-token",
                "CLOUDFLARE_ACCOUNT_ID": "abc123",
            },
            clear=True,
        ):
            router = FreeCloudRouter()
            providers = {provider.name: provider for provider in router.providers()}

        self.assertIn("cloudflare", providers)
        self.assertEqual(
            providers["cloudflare"].base_url,
            "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1",
        )
        self.assertEqual(providers["cloudflare"].api_key, "test-token")
        self.assertFalse(providers["cloudflare"].allow_confidential)

    async def test_cloudflare_provider_is_dormant_when_configuration_is_incomplete(self):
        for environment in (
            {"CLOUDFLARE_API_TOKEN": "token-only"},
            {"CLOUDFLARE_ACCOUNT_ID": "account-only"},
            {},
        ):
            with self.subTest(environment=environment), patch.dict(
                os.environ,
                environment,
                clear=True,
            ):
                router = FreeCloudRouter()
                self.assertNotIn(
                    "cloudflare",
                    {provider.name for provider in router.providers()},
                )

    async def test_direct_provider_remains_ineligible_until_free_account_is_verified(self):
        with patch.dict(os.environ, {}, clear=True):
            router = FreeCloudRouter()
            self.assertEqual(
                router._eligible(
                    "@cf/openai/gpt-oss-20b",
                    "cloudflare",
                    "cloudflare",
                ),
                (False, "cost-not-verified-zero"),
            )

        with patch.dict(
            os.environ,
            {"KMJ_VERIFIED_FREE_PROVIDERS": "cloudflare"},
            clear=True,
        ):
            router = FreeCloudRouter()
            self.assertEqual(
                router._eligible(
                    "@cf/openai/gpt-oss-20b",
                    "cloudflare",
                    "cloudflare",
                ),
                (True, "verified-free-provider-account"),
            )

    async def test_local_aggregator_headers_follow_data_classification(self):
        router = FreeCloudRouter()
        local = ProviderEndpoint(
            name="9router",
            base_url="http://127.0.0.1:18765/v1",
        )
        direct = ProviderEndpoint(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key="test",
        )
        self.assertEqual(
            router._provider_headers(local, "public")["X-KMJ-Sensitivity"],
            "public",
        )
        self.assertEqual(
            router._provider_headers(local, "confidential")[
                "X-KMJ-Sensitivity"
            ],
            "confidential",
        )
        self.assertNotIn(
            "X-KMJ-Sensitivity",
            router._provider_headers(direct, "public"),
        )

    async def test_invalid_classification_fails_closed_to_confidential(self):
        router = FreeCloudRouter()
        self.assertEqual(
            router._normalize_classification("unexpected"),
            "confidential",
        )

    async def test_local_9router_is_public_only_by_default(self):
        router = FreeCloudRouter()
        local = next(provider for provider in router.providers() if provider.name == "9router")
        self.assertFalse(local.allow_confidential)

    async def test_confidential_workload_never_falls_back_to_unverified_free_client(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        with patch("controller.opencode_free.complete") as client:
            with self.assertRaisesRegex(
                NoFreeRouteAvailable,
                "NO_CONFIDENTIAL_FREE_ROUTE_AVAILABLE",
            ):
                await router.complete(
                    [{"role": "user", "content": "private source"}],
                    data_classification="confidential",
                )
            client.assert_not_called()

    async def test_explicit_opencode_free_model_is_zero_cost_allowlisted_for_public_route(self):
        router = FreeCloudRouter()
        self.assertEqual(
            router._eligible(
                "oc/muse-spark-1.3-contributor-free",
                "opencode",
                "9router",
            ),
            (True, "explicit-zero-allowlist"),
        )

    async def test_empty_http_catalog_uses_official_client_result(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        expected = {"model": "opencode/big-pickle", "response": {"choices": []}}
        with patch("controller.opencode_free.complete", return_value=expected) as client:
            self.assertEqual(
                await router.complete(
                    [{"role": "user", "content": "test"}],
                    data_classification="public",
                ),
                expected,
            )
            client.assert_called_once_with([{"role": "user", "content": "test"}])

    async def test_unavailable_official_client_preserves_fail_closed(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        with patch("controller.opencode_free.complete", side_effect=OpenCodeUnavailable("OPENCODE_COST_NOT_VERIFIED_ZERO")):
            with self.assertRaisesRegex(NoFreeRouteAvailable, "COST_NOT_VERIFIED_ZERO"):
                await router.complete([], data_classification="public")

    async def test_disabled_client_cannot_be_selected_as_free(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(NoFreeRouteAvailable, "NOT_CONFIGURED"):
                await router.complete([], data_classification="public")


if __name__ == "__main__":
    unittest.main()
