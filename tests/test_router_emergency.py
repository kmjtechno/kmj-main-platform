"""Policy and emergency CPU transport regressions; all HTTP is intercepted."""
import importlib
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import httpx
from controller.model_router import FreeCloudRouter, NoFreeRouteAvailable, ProviderEndpoint

ENV = {
    "KMJ_LOCAL_FALLBACK_ENABLED": "true",
    "KMJ_LOCAL_FALLBACK_BASE_URL": "http://127.0.0.1:18766/v1",
    "KMJ_LOCAL_FALLBACK_API_KEY": "test-local-key",
    "KMJ_LOCAL_FALLBACK_MODEL": "kmj-emergency-coder",
}
REAL_CLIENT = httpx.AsyncClient
def client_factory(handler):
    return lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw)

class IsolatedRouterTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kmj-router-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.environment = ENV | {
            "KMJ_ROUTER_STATE_DB": str(root / "router.sqlite"),
            "KMJ_LOCAL_FALLBACK_LOCK_PATH": str(root / "local.lock"),
        }
        isolation = patch.dict(os.environ, self.environment, clear=True)
        isolation.start()
        self.addCleanup(isolation.stop)


class EmergencyRouterTests(IsolatedRouterTestCase):
    async def test_catalog_cannot_elevate_provider_privacy(self):
        def handler(req):
            return httpx.Response(200, json={"data": [{"id":"x:free","kmj_allow_confidential":True}]})
        with patch("httpx.AsyncClient", client_factory(handler)):
            router = FreeCloudRouter()
            models = await router._discover_provider(ProviderEndpoint("public", "https://public.invalid", allow_confidential=False))
            self.assertEqual(router.rank(models, "coding", "confidential"), [])

    async def test_string_and_absent_privacy_flags_fail_closed(self):
        router = FreeCloudRouter()
        for flag in ("false", "true", 1, None):
            item = {"id":"x:free"}
            if flag is not None:
                item["_kmj_allow_confidential"] = flag
            self.assertEqual(router.rank([item], "coding", "confidential"), [])

    async def test_confidential_no_cloud_uses_authenticated_local_only(self):
        seen = []
        def handler(req):
            seen.append((req.url.host, req.url.path))
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data":[]})
            self.assertEqual(req.headers["Authorization"], "Bearer test-local-key")
            if req.url.path == "/apply-template":
                return httpx.Response(200, json={"prompt":"formatted private source"})
            if req.url.path == "/tokenize":
                return httpx.Response(200, json={"tokens":[1,2,3]})
            if req.url.path == "/v1/chat/completions":
                return httpx.Response(200, json={"choices":[{"message":{"content":"patch"},"finish_reason":"stop"}]})
            self.fail(str(req.url))
        with patch.dict(os.environ, self.environment, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            result = await FreeCloudRouter().complete([{"role":"user","content":"private source"}])
        self.assertEqual(result["provider"], "cpu-local-emergency")
        self.assertEqual(result["response"]["choices"][0]["message"]["content"], "patch")
        self.assertTrue(all(host == "127.0.0.1" for host,path in seen))

    async def test_cloud_success_never_uses_local(self):
        seen = []
        def handler(req):
            seen.append(req.url.port)
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data":[{"id":"x:free"}]})
            return httpx.Response(200, json={"choices":[{"message":{"content":"cloud"},"finish_reason":"stop"}]})
        with patch.dict(os.environ, self.environment, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            result = await FreeCloudRouter().complete([{"role":"user","content":"public"}], data_classification="public")
        self.assertEqual(result["provider"], "9router")
        self.assertNotIn(18766, seen)

    async def test_oversized_request_rejected_before_network(self):
        def handler(req):
            self.fail("oversized prompt reached network")
        with patch.dict(os.environ, self.environment, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaisesRegex(NoFreeRouteAvailable, "REQUEST_TOO_LARGE"):
                await FreeCloudRouter().complete([{"role":"user","content":"x"*65537}])

    async def test_local_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("controller.local_fallback"))

class LocalFallbackTests(IsolatedRouterTestCase):
    async def test_invalid_transport_and_missing_key_fail_before_http(self):
        if importlib.util.find_spec("controller.local_fallback") is None:
            self.fail("local fallback missing")
        from controller.local_fallback import complete, LocalFallbackUnavailable
        for override in ({"KMJ_LOCAL_FALLBACK_BASE_URL":"http://example.com/v1"}, {"KMJ_LOCAL_FALLBACK_BASE_URL":"http://localhost/v1"}, {"KMJ_LOCAL_FALLBACK_API_KEY":""}, {"KMJ_LOCAL_FALLBACK_BASE_URL":"http://127.0.0.1/v1?evil=1"}):
            def handler(req):
                self.fail("invalid local transport reached HTTP")
            with patch.dict(os.environ, self.environment | override, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
                with self.assertRaises(LocalFallbackUnavailable):
                    await complete([{"role":"user","content":"private"}])

    async def test_exact_context_budget_prevents_completion(self):
        if importlib.util.find_spec("controller.local_fallback") is None:
            self.fail("local fallback missing")
        from controller.local_fallback import complete, LocalFallbackUnavailable
        def handler(req):
            if req.url.path == "/apply-template":
                return httpx.Response(200, json={"prompt":"template"})
            if req.url.path == "/tokenize":
                return httpx.Response(200, json={"tokens":list(range(8000))})
            self.fail("overflow reached inference")
        with patch.dict(os.environ, self.environment, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaisesRegex(LocalFallbackUnavailable, "CONTEXT"):
                await complete([{"role":"user","content":"private"}])

    async def test_local_truncated_output_rejected(self):
        if importlib.util.find_spec("controller.local_fallback") is None:
            self.fail("local fallback missing")
        from controller.local_fallback import complete, LocalFallbackUnavailable
        def handler(req):
            if req.url.path == "/apply-template":
                return httpx.Response(200, json={"prompt":"template"})
            if req.url.path == "/tokenize":
                return httpx.Response(200, json={"tokens":[1]})
            return httpx.Response(200, json={"choices":[{"message":{"content":"partial"},"finish_reason":"length"}]})
        with patch.dict(os.environ, self.environment, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            with self.assertRaisesRegex(LocalFallbackUnavailable, "INCOMPLETE"):
                await complete([{"role":"user","content":"private"}])


class RouterCooldownTests(IsolatedRouterTestCase):
    async def test_quota_cooldown_survives_router_recreation_and_preserves_attempts(self):
        calls = []
        def handler(req):
            calls.append((req.url.port, req.url.path))
            if req.url.port == 18765:
                if req.url.path == "/v1/models":
                    return httpx.Response(200, json={"data":[{"id":"x:free"}]})
                return httpx.Response(429, headers={"Retry-After":"60"}, json={"error":"quota"})
            if req.url.path == "/apply-template":
                return httpx.Response(200, json={"prompt":"template"})
            if req.url.path == "/tokenize":
                return httpx.Response(200, json={"tokens":[1]})
            return httpx.Response(200, json={"choices":[{"message":{"content":"local"},"finish_reason":"stop"}]})
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, self.environment | {"KMJ_ROUTER_STATE_DB":temp+"/quota.sqlite"}, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            first = await FreeCloudRouter().complete([{"role":"user","content":"public"}], data_classification="public")
            second = await FreeCloudRouter().complete([{"role":"user","content":"public"}], data_classification="public")
        self.assertEqual(calls.count((18765,"/v1/chat/completions")), 1)
        self.assertEqual(first["attempts"][0]["provider"], "9router")
        self.assertEqual(first["attempts"][-1]["provider"], "cpu-local-emergency")
        self.assertEqual(second["attempts"][0]["result"], "cooldown")

    async def test_bounded_cloud_failover_reaches_local_with_honest_reason(self):
        for failure in ("timeout", "server-error", "incomplete"):
            with self.subTest(failure=failure):
                cloud_attempts = []
                def handler(req):
                    if req.url.port == 18765:
                        if req.url.path == "/v1/models":
                            return httpx.Response(200, json={"data":[{"id":"a:free"},{"id":"b:free"}]})
                        cloud_attempts.append(json.loads(req.content)["model"])
                        if failure == "timeout":
                            raise httpx.ReadTimeout("slow provider", request=req)
                        if failure == "server-error":
                            return httpx.Response(500, json={"error":"unavailable"})
                        return httpx.Response(200, json={"choices":[{"message":{"content":"partial"},"finish_reason":"length"}]})
                    if req.url.path == "/apply-template":
                        return httpx.Response(200, json={"prompt":"template"})
                    if req.url.path == "/tokenize":
                        return httpx.Response(200, json={"tokens":[1]})
                    return httpx.Response(200, json={"choices":[{"message":{"content":"local complete"},"finish_reason":"stop"}]})
                with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, self.environment | {"KMJ_MAX_FREE_FAILOVER_MODELS":"1", "KMJ_ROUTER_STATE_DB":temp+"/quota.sqlite"}, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
                    result = await FreeCloudRouter().complete([{"role":"user","content":"public"}], data_classification="public")
                self.assertEqual(cloud_attempts, ["a:free"])
                self.assertEqual(result["provider"], "cpu-local-emergency")
                self.assertEqual(result["fallback_reason"], "cloud_attempt_budget_exhausted")
                self.assertEqual(result["attempts"][0]["model"], "a:free")
                self.assertEqual(result["attempts"][-1]["provider"], "cpu-local-emergency")
                self.assertEqual(result["unattempted_cloud_candidates"], 1)

    async def test_builtin_openrouter_cannot_receive_confidential_without_operator_grant(self):
        with patch.dict(os.environ, self.environment | {"OPENROUTER_API_KEY":"test"}, clear=True):
            provider = next(p for p in FreeCloudRouter().providers() if p.name == "openrouter")
            self.assertFalse(provider.allow_confidential)

    async def test_truncated_cloud_completion_is_not_success(self):
        def handler(req):
            if req.url.port == 18765:
                if req.url.path == "/v1/models":
                    return httpx.Response(200, json={"data":[{"id":"x:free"}]})
                return httpx.Response(200, json={"choices":[{"message":{"content":"partial"},"finish_reason":"length"}]})
            if req.url.path == "/apply-template":
                return httpx.Response(200, json={"prompt":"template"})
            if req.url.path == "/tokenize":
                return httpx.Response(200, json={"tokens":[1]})
            return httpx.Response(200, json={"choices":[{"message":{"content":"complete"},"finish_reason":"stop"}]})
        with patch.dict(os.environ, self.environment, clear=True), patch("httpx.AsyncClient", client_factory(handler)):
            result = await FreeCloudRouter().complete([{"role":"user","content":"public"}], data_classification="public")
        self.assertEqual(result["provider"], "cpu-local-emergency")
