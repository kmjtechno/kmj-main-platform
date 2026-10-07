"""Cloud-only ModelFabric routing and fail-closed regression tests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from controller.model_router import FreeCloudRouter, NoFreeRouteAvailable, ProviderEndpoint


REAL_CLIENT = httpx.AsyncClient


def client_factory(handler):
    return lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw)


class IsolatedRouterTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kmj-router-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.environment = {
            "KMJ_ROUTER_STATE_DB": str(root / "router.sqlite"),
            # These legacy values must never re-enable local inference.
            "KMJ_LOCAL_FALLBACK_ENABLED": "true",
            "KMJ_LOCAL_FALLBACK_BASE_URL": "http://127.0.0.1:18766/v1",
            "KMJ_LOCAL_FALLBACK_API_KEY": "must-be-ignored",
        }
        isolation = patch.dict(os.environ, self.environment, clear=True)
        isolation.start()
        self.addCleanup(isolation.stop)


class CloudOnlyRouterTests(IsolatedRouterTestCase):
    async def test_policy_is_explicitly_cloud_only(self):
        router = FreeCloudRouter()
        self.assertEqual(router.config["policy"]["generative_ai"], "cloud_only")
        self.assertEqual(router.config["policy"]["local_llm"], "prohibited")

    async def test_catalog_cannot_elevate_provider_privacy(self):
        def handler(req):
            return httpx.Response(
                200,
                json={"data": [{"id": "x:free", "kmj_allow_confidential": True}]},
            )
        with patch("httpx.AsyncClient", client_factory(handler)):
            router = FreeCloudRouter()
            models = await router._discover_provider(
                ProviderEndpoint(
                    "public",
                    "https://public.invalid",
                    allow_confidential=False,
                )
            )
            self.assertEqual(router.rank(models, "coding", "confidential"), [])

    async def test_string_and_absent_privacy_flags_fail_closed(self):
        router = FreeCloudRouter()
        for flag in ("false", "true", 1, None):
            item = {"id": "x:free"}
            if flag is not None:
                item["_kmj_allow_confidential"] = flag
            self.assertEqual(router.rank([item], "coding", "confidential"), [])

    async def test_confidential_without_eligible_cloud_fails_closed_even_if_local_env_exists(self):
        seen = []

        def handler(req):
            seen.append((req.url.host, req.url.port, req.url.path))
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data": []})
            self.fail("no completion transport should be called")

        with patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaisesRegex(
                NoFreeRouteAvailable,
                "NO_CONFIDENTIAL_FREE_ROUTE_AVAILABLE",
            ):
                await FreeCloudRouter().complete(
                    [{"role": "user", "content": "private source"}],
                    data_classification="confidential",
                )
        self.assertFalse(any(port == 18766 for _host, port, _path in seen))

    async def test_cloud_success_never_uses_local(self):
        seen = []

        def handler(req):
            seen.append(req.url.port)
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "x:free"}]})
            return httpx.Response(
                200,
                json={
                    "choices": [{
                        "message": {"content": "cloud"},
                        "finish_reason": "stop",
                    }]
                },
            )

        with patch("httpx.AsyncClient", client_factory(handler)):
            result = await FreeCloudRouter().complete(
                [{"role": "user", "content": "public"}],
                data_classification="public",
            )
        self.assertEqual(result["provider"], "9router")
        self.assertNotIn(18766, seen)

    async def test_oversized_request_rejected_before_network(self):
        def handler(req):
            self.fail("oversized prompt reached network")

        with patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaisesRegex(NoFreeRouteAvailable, "REQUEST_TOO_LARGE"):
                await FreeCloudRouter().complete(
                    [{"role": "user", "content": "x" * 65537}]
                )

    async def test_quota_cooldown_survives_router_recreation_without_local_fallback(self):
        calls = []

        def handler(req):
            calls.append((req.url.port, req.url.path))
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "x:free"}]})
            return httpx.Response(
                429,
                headers={"Retry-After": "60"},
                json={"error": "quota"},
            )

        with patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaises(NoFreeRouteAvailable):
                await FreeCloudRouter().complete(
                    [{"role": "user", "content": "public"}],
                    data_classification="public",
                )
            with self.assertRaises(NoFreeRouteAvailable):
                await FreeCloudRouter().complete(
                    [{"role": "user", "content": "public"}],
                    data_classification="public",
                )
        self.assertEqual(calls.count((18765, "/v1/chat/completions")), 1)
        self.assertNotIn((18766, "/v1/chat/completions"), calls)

    async def test_bounded_cloud_failover_never_crosses_into_local_inference(self):
        for failure in ("timeout", "server-error", "incomplete"):
            with self.subTest(failure=failure):
                cloud_attempts = []

                def handler(req):
                    if req.url.port == 18766:
                        self.fail("local inference transport was attempted")
                    if req.url.path == "/v1/models":
                        return httpx.Response(
                            200,
                            json={"data": [{"id": "a:free"}, {"id": "b:free"}]},
                        )
                    cloud_attempts.append(json.loads(req.content)["model"])
                    if failure == "timeout":
                        raise httpx.ReadTimeout("slow provider", request=req)
                    if failure == "server-error":
                        return httpx.Response(500, json={"error": "unavailable"})
                    return httpx.Response(
                        200,
                        json={
                            "choices": [{
                                "message": {"content": "partial"},
                                "finish_reason": "length",
                            }]
                        },
                    )

                with patch.dict(
                    os.environ,
                    self.environment | {"KMJ_MAX_FREE_FAILOVER_MODELS": "1"},
                    clear=True,
                ), patch("httpx.AsyncClient", client_factory(handler)):
                    with self.assertRaises(NoFreeRouteAvailable):
                        await FreeCloudRouter().complete(
                            [{"role": "user", "content": "public"}],
                            data_classification="public",
                        )
                self.assertEqual(len(cloud_attempts), 1)
                self.assertIn(cloud_attempts[0], {"a:free", "b:free"})

    async def test_builtin_openrouter_cannot_receive_confidential_without_operator_grant(self):
        with patch.dict(
            os.environ,
            self.environment | {"OPENROUTER_API_KEY": "test"},
            clear=True,
        ):
            provider = next(
                p for p in FreeCloudRouter().providers()
                if p.name == "openrouter"
            )
            self.assertFalse(provider.allow_confidential)

    async def test_truncated_cloud_completion_is_not_success(self):
        def handler(req):
            if req.url.port == 18766:
                self.fail("local inference transport was attempted")
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "x:free"}]})
            return httpx.Response(
                200,
                json={
                    "choices": [{
                        "message": {"content": "partial"},
                        "finish_reason": "length",
                    }]
                },
            )

        with patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaises(NoFreeRouteAvailable):
                await FreeCloudRouter().complete(
                    [{"role": "user", "content": "public"}],
                    data_classification="public",
                )


if __name__ == "__main__":
    unittest.main()
