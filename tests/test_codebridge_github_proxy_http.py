from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import controller.main as main

SECRET = "p" * 48
ENV = {
    "KMJ_CODEBRIDGE_GITHUB_PROXY_TOKEN": SECRET,
    "KMJ_CODEBRIDGE_GITHUB_REPOSITORIES": "kmjtechno/kmj-codebridge",
    "GITHUB_TOKEN": "g" * 40,
}


class _Upstream:
    def __init__(self, status: int = 200, content: bytes = b"{}") -> None:
        self.status_code = status
        self.content = content
        self.headers = {"content-type": "application/json"}


class _Client:
    calls: list[tuple[str, str, bytes | None, dict]] = []
    response = _Upstream()

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def request(self, method, url, headers=None, content=None):
        _Client.calls.append((method, url, content, dict(headers or {})))
        return _Client.response


class CodeBridgeGitHubProxyHttpTest(unittest.TestCase):
    def setUp(self) -> None:
        _Client.calls = []
        _Client.response = _Upstream()
        self.env = patch.dict(os.environ, ENV, clear=False)
        self.env.start()
        self.client_patch = patch.object(main.httpx, "AsyncClient", _Client)
        self.client_patch.start()
        self.http = TestClient(main.app)
        self.auth = {"Authorization": f"Bearer {SECRET}"}

    def tearDown(self) -> None:
        self.client_patch.stop()
        self.env.stop()

    def test_merge_put_is_forwarded_with_exact_sha_and_server_credential(self) -> None:
        body = {"sha": "a" * 40, "merge_method": "squash"}
        res = self.http.put(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/pulls/7/merge",
            json=body,
            headers=self.auth,
        )
        self.assertEqual(res.status_code, 200)
        method, url, _content, headers = _Client.calls[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(
            url, "https://api.github.com/repos/kmjtechno/kmj-codebridge/pulls/7/merge"
        )
        self.assertEqual(headers["Authorization"], "Bearer " + "g" * 40)

    def test_approve_review_and_workflow_write_never_reach_github(self) -> None:
        review = self.http.post(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/pulls/7/reviews",
            json={"event": "APPROVE", "body": "lgtm"},
            headers=self.auth,
        )
        self.assertEqual(review.status_code, 400)
        workflow = self.http.put(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/.github/workflows/x.yml",
            json={"message": "m", "content": "aGk=", "branch": "x"},
            headers=self.auth,
        )
        self.assertEqual(workflow.status_code, 405)
        self.assertEqual(_Client.calls, [])

    def test_auth_and_repository_allowlist_are_enforced(self) -> None:
        path = "/codebridge/github/repos/kmjtechno/kmj-codebridge/pulls?state=open"
        self.assertEqual(self.http.get(path).status_code, 401)
        self.assertEqual(
            self.http.get(path, headers={"Authorization": "Bearer wrong"}).status_code,
            403,
        )
        other = self.http.get(
            "/codebridge/github/repos/kmjtechno/other/pulls", headers=self.auth
        )
        self.assertEqual(other.status_code, 404)
        self.assertEqual(self.http.get(path, headers=self.auth).status_code, 200)
        self.assertEqual(len(_Client.calls), 1)

    def test_content_path_is_percent_encoded_upstream(self) -> None:
        self.http.put(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/docs/a%20b.md",
            json={"message": "m", "content": "aGk=", "branch": "feature/x"},
            headers=self.auth,
        )
        self.assertTrue(_Client.calls[0][1].endswith("/contents/docs/a%20b.md"))

    def test_large_list_responses_up_to_limit_are_returned(self) -> None:
        _Client.response = _Upstream(content=b"[" + b'"x",' * 200000 + b'"x"]')
        res = self.http.get(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/pulls?per_page=30",
            headers=self.auth,
        )
        self.assertEqual(res.status_code, 200)
        _Client.response = _Upstream(
            content=b"x" * (main.CODEBRIDGE_GITHUB_RESPONSE_MAX_BYTES + 1)
        )
        res = self.http.get(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/pulls", headers=self.auth
        )
        self.assertEqual(res.status_code, 413)


if __name__ == "__main__":
    unittest.main()
