"""Model availability memory must never weaken cost or privacy eligibility."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from controller.model_router import FreeCloudRouter


class RouterModelHealthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "health.db"
        self.env = patch.dict(os.environ, {"KMJ_ROUTER_STATE_DB": str(self.db)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def model(self, name, provider="one", base="https://one.invalid", private=False):
        return {"id": name, "_kmj_provider": provider, "_kmj_base_url": base,
                "_kmj_allow_confidential": private}

    def router(self, models):
        router = FreeCloudRouter()
        router.config = {"routes": {"coding": {"prefer": ["a:free"]}}}
        router.discover = AsyncMock(return_value=models)
        router._final_fallback = AsyncMock(return_value={"provider": "fallback"})
        return router

    async def complete(self, router, handler, classification="public"):
        client_type = httpx.AsyncClient
        with patch("controller.model_router.httpx.AsyncClient",
                   side_effect=lambda **kwargs: client_type(
                       transport=httpx.MockTransport(handler), **kwargs)):
            return await router.complete([{"role": "user", "content": "bounded task"}],
                                         data_classification=classification)

    def success(self, request):
        return httpx.Response(200, request=request, json={
            "choices": [{"finish_reason": "stop", "message": {"content": "done"}}]})

    async def test_404_persists_model_only_cooldown_across_instances(self):
        models = [self.model("a:free"), self.model("b:free"),
                  self.model("a:free", "two", "https://two.invalid")]
        seen = []
        def handler(request):
            model = json.loads(request.content)["model"]
            seen.append((request.url.host, model))
            if request.url.host == "one.invalid" and model == "a:free":
                return httpx.Response(404, request=request)
            return self.success(request)
        await self.complete(self.router(models), handler)
        seen.clear()
        second = await self.complete(self.router(models), handler)
        self.assertNotIn(("one.invalid", "a:free"), seen)
        self.assertEqual(second["provider"], "two")
        isolated = await self.complete(self.router([models[0]]), self.success)
        self.assertEqual(isolated["provider"], "fallback")
        different_endpoint = self.model("a:free", "one", "https://other.invalid")
        healthy = await self.complete(self.router([different_endpoint]), self.success)
        self.assertEqual(healthy["model"], "a:free")
        # A healthy sibling model on the cooled model's endpoint still works.
        sibling = await self.complete(self.router([models[1]]), handler)
        self.assertEqual(sibling["model"], "b:free")

    async def test_real_success_is_preferred_on_next_request(self):
        a, b = self.model("a:free"), self.model("b:free")
        await self.complete(self.router([b]), self.success)
        result = await self.complete(self.router([a, b]), self.success)
        self.assertEqual(result["model"], "b:free")

    async def test_success_memory_never_admits_paid_or_private_ineligible_models(self):
        public_model = self.model("winner:free")
        await self.complete(self.router([public_model]), self.success)
        confidential = await self.complete(self.router([public_model]), self.success, "confidential")
        self.assertEqual(confidential["provider"], "fallback")
        # The same previously successful ID loses eligibility when policy denies it.
        router = self.router([public_model])
        router.config["deny"] = {"model_fragments": ["winner"]}
        self.assertEqual((await self.complete(router, self.success))["provider"], "fallback")
        paid = self.model("paid-model")
        router = self.router([paid])
        router.config["verified_zero"] = {"explicit_models": ["paid-model"]}
        await self.complete(router, self.success)
        self.assertEqual((await self.complete(self.router([paid]), self.success))["provider"], "fallback")

    async def test_timeout_and_incomplete_response_get_short_model_cooldown(self):
        for failure in ("timeout", "incomplete"):
            with self.subTest(failure=failure):
                model = self.model(failure + ":free")
                def handler(request):
                    if failure == "timeout":
                        raise httpx.ReadTimeout("sensitive provider detail", request=request)
                    return httpx.Response(200, request=request, json={
                        "choices": [{"finish_reason": "length", "message": {"content": "partial"}}]})
                with patch("controller.model_router.time.time", return_value=100):
                    await self.complete(self.router([model]), handler)
                    result = await self.complete(self.router([model]), self.success)
                self.assertEqual(result["provider"], "fallback")
                with patch("controller.model_router.time.time", return_value=161):
                    recovered = await self.complete(self.router([model]), self.success)
                self.assertEqual(recovered["model"], model["id"])

    async def test_success_preference_expires(self):
        a, b = self.model("a:free"), self.model("b:free")
        with patch("controller.model_router.time.time", return_value=100):
            await self.complete(self.router([b]), self.success)
        with patch("controller.model_router.time.time", return_value=3701):
            result = await self.complete(self.router([a, b]), self.success)
        self.assertEqual(result["model"], "a:free")


if __name__ == "__main__":
    unittest.main()
