import os
import unittest
from unittest.mock import AsyncMock, patch

from controller.model_router import FreeCloudRouter, NoFreeRouteAvailable
from controller.opencode_free import OpenCodeUnavailable


class RouterOfficialClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_http_catalog_uses_official_client_result(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        expected = {"model": "opencode/big-pickle", "response": {"choices": []}}
        with patch("controller.opencode_free.complete", return_value=expected) as client:
            self.assertEqual(await router.complete([{"role": "user", "content": "test"}]), expected)
            client.assert_called_once_with([{"role": "user", "content": "test"}])

    async def test_unavailable_official_client_preserves_fail_closed(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        with patch("controller.opencode_free.complete", side_effect=OpenCodeUnavailable("OPENCODE_COST_NOT_VERIFIED_ZERO")):
            with self.assertRaisesRegex(NoFreeRouteAvailable, "COST_NOT_VERIFIED_ZERO"):
                await router.complete([])

    async def test_disabled_client_cannot_be_selected_as_free(self):
        router = FreeCloudRouter()
        router.discover = AsyncMock(return_value=[])
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(NoFreeRouteAvailable, "NOT_CONFIGURED"):
                await router.complete([])


if __name__ == "__main__":
    unittest.main()
