from __future__ import annotations

import os
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import controller.main as main

SECRET = "p" * 48
ENV = {
    "KMJ_CODEBRIDGE_GITHUB_PROXY_TOKEN": SECRET,
    "KMJ_CODEBRIDGE_GITHUB_REPOSITORIES": "kmjtechno/kmj-codebridge",
    "GITHUB_TOKEN": "g" * 40,
    "KMJ_CODEBRIDGE_GITHUB_WRITE_BRANCHES": json.dumps({'kmjtechno/kmj-codebridge': ['codebridge/test']}),
}


class _Upstream:
    def __init__(self, status: int = 200, content: bytes = b"{}") -> None:
        self.status_code = status
        self.content = content
        self.headers = {"content-type": "application/json"}


class _Client:
    calls: list[tuple[str, str, bytes | None, dict]] = []
    response = _Upstream()
    default_branch = 'main'
    protected = False
    metadata_status = 200
    branch_status = 200

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def request(self, method, url, headers=None, content=None):
        _Client.calls.append((method, url, content, dict(headers or {})))
        if method == 'GET' and '/branches/' in url:
            return _Upstream(_Client.branch_status, json.dumps({'protected': _Client.protected}).encode())
        if method == 'GET' and url == 'https://api.github.com/repos/kmjtechno/kmj-codebridge':
            return _Upstream(_Client.metadata_status, json.dumps({'default_branch': _Client.default_branch}).encode())
        return _Client.response


class CodeBridgeGitHubProxyHttpTest(unittest.TestCase):
    def test_duplicate_queries_never_reach_github(self) -> None:
        for query in ('per_page=1000&per_page=1', 'sha=other&sha=main', 'per_page=1&per_page=1'):
            with self.subTest(query=query):
                res = self.http.get('/codebridge/github/repos/kmjtechno/kmj-codebridge/commits?' + query, headers=self.auth)
                self.assertEqual(res.status_code, 400)
        self.assertEqual(_Client.calls, [])

    def test_content_writes_default_to_denied(self) -> None:
        with patch.dict(os.environ, {'KMJ_CODEBRIDGE_GITHUB_WRITE_BRANCHES': ''}):
            res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': 'feature/x'}, headers=self.auth)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(_Client.calls, [])

    def test_protected_branches_cannot_be_granted(self) -> None:
        for branch in ('main', 'master', 'staging-approved', 'production', 'release/v1', 'refs/heads/main'):
            with self.subTest(branch=branch), patch.dict(os.environ, {'KMJ_CODEBRIDGE_GITHUB_WRITE_BRANCHES': json.dumps({'kmjtechno/kmj-codebridge': [branch]})}):
                res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': branch}, headers=self.auth)
                self.assertEqual(res.status_code, 403)
        self.assertEqual(_Client.calls, [])

    def test_branch_grants_are_repository_scoped_and_exact(self) -> None:
        grants = json.dumps({'kmjtechno/other': ['feature/x'], 'kmjtechno/kmj-codebridge': ['feature/y']})
        with patch.dict(os.environ, {'KMJ_CODEBRIDGE_GITHUB_WRITE_BRANCHES': grants}):
            res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': 'feature/x'}, headers=self.auth)
            self.assertEqual(res.status_code, 403)
        self.assertEqual(_Client.calls, [])

    def test_exact_granted_development_branch_can_be_created(self) -> None:
        res = self.http.post('/codebridge/github/repos/kmjtechno/kmj-codebridge/git/refs', json={'ref': 'refs/heads/codebridge/test', 'sha': 'a' * 40}, headers=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(_Client.calls), 3)
        self.assertEqual(_Client.calls[-1][3]['Authorization'], 'Bearer ' + 'g' * 40)

    def test_ungranted_branch_creation_is_denied(self) -> None:
        for branch in ('main', 'codebridge/test-more', 'codebridge/other'):
            with self.subTest(branch=branch):
                res = self.http.post('/codebridge/github/repos/kmjtechno/kmj-codebridge/git/refs', json={'ref': 'refs/heads/' + branch, 'sha': 'a' * 40}, headers=self.auth)
                self.assertEqual(res.status_code, 403)
        self.assertEqual(_Client.calls, [])

    def test_invalid_or_ambiguous_grants_are_denied(self) -> None:
        for grants in ('not-json', '[]', '{"kmjtechno/kmj-codebridge": "codebridge/test"}', '{"kmjtechno/kmj-codebridge": [], "kmjtechno/kmj-codebridge": ["codebridge/test"]}'):
            with self.subTest(grants=grants), patch.dict(os.environ, {'KMJ_CODEBRIDGE_GITHUB_WRITE_BRANCHES': grants}):
                res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': 'codebridge/test'}, headers=self.auth)
                self.assertEqual(res.status_code, 403)
        self.assertEqual(_Client.calls, [])

    def test_ci_entry_point_writes_are_denied_on_granted_branch(self) -> None:
        for path in ('.github/actions/build/action.yml', 'scripts/build.py', 'apps/foo/scripts/build.py', 'Jenkinsfile', '.gitlab-ci.yml', '.circleci/config.yml', '.buildkite/pipeline.yml', 'package.json', 'apps/platform/package.json', '.npmrc', 'requirements.txt'):
            with self.subTest(path=path):
                res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/' + path, json={'message': 'm', 'content': 'aGk=', 'branch': 'codebridge/test'}, headers=self.auth)
                self.assertEqual(res.status_code, 405)
        self.assertEqual(_Client.calls, [])

    def test_duplicate_body_keys_are_denied(self) -> None:
        res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', content='{"message":"m","content":"aGk=","branch":"main","branch":"codebridge/test"}', headers={**self.auth, 'Content-Type': 'application/json'})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(_Client.calls, [])

    def test_validated_query_is_canonically_encoded(self) -> None:
        res = self.http.get('/codebridge/github/repos/kmjtechno/kmj-codebridge/commits?sha=codebridge%2Ftest&per_page=%31', headers=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(_Client.calls[0][1].endswith('?sha=codebridge%2Ftest&per_page=1'))

    def setUp(self) -> None:
        _Client.calls = []
        _Client.response = _Upstream()
        _Client.default_branch = 'main'
        _Client.protected = False
        _Client.metadata_status = 200
        _Client.branch_status = 200
        self.env = patch.dict(os.environ, ENV, clear=False)
        self.env.start()
        self.client_patch = patch.object(main.httpx, "AsyncClient", _Client)
        self.client_patch.start()
        self.http = TestClient(main.app)
        self.auth = {"Authorization": f"Bearer {SECRET}"}

    def tearDown(self) -> None:
        self.client_patch.stop()
        self.env.stop()

    def test_merge_is_denied_even_with_exact_sha_and_server_credential(self) -> None:
        body = {"sha": "a" * 40, "merge_method": "squash"}
        res = self.http.put(
            "/codebridge/github/repos/kmjtechno/kmj-codebridge/pulls/7/merge",
            json=body,
            headers=self.auth,
        )
        self.assertEqual(res.status_code, 405)
        self.assertEqual(_Client.calls, [])

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
            json={"message": "m", "content": "aGk=", "branch": "codebridge/test"},
            headers=self.auth,
        )
        self.assertTrue(_Client.calls[-1][1].endswith("/contents/docs/a%20b.md"))

    def test_default_or_protected_development_branch_cannot_be_written(self) -> None:
        for default, protected in [('codebridge/test', False), ('main', True)]:
            with self.subTest(default=default, protected=protected):
                _Client.calls = []
                _Client.default_branch = default
                _Client.protected = protected
                res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': 'codebridge/test'}, headers=self.auth)
                self.assertEqual(res.status_code, 403)
                self.assertTrue(all(call[0] == 'GET' for call in _Client.calls))

    def test_unavailable_branch_metadata_blocks_mutation(self) -> None:
        for status in (403, 429, 500):
            with self.subTest(status=status):
                _Client.calls = []
                _Client.metadata_status = status
                res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': 'codebridge/test'}, headers=self.auth)
                self.assertEqual(res.status_code, 503)
                self.assertTrue(all(call[0] == 'GET' for call in _Client.calls))

    def test_missing_branch_is_allowed_only_for_explicit_creation(self) -> None:
        _Client.branch_status = 404
        res = self.http.post('/codebridge/github/repos/kmjtechno/kmj-codebridge/git/refs', json={'ref': 'refs/heads/codebridge/test', 'sha': 'a' * 40}, headers=self.auth)
        self.assertEqual(res.status_code, 200)
        _Client.calls = []
        res = self.http.put('/codebridge/github/repos/kmjtechno/kmj-codebridge/contents/src/a.py', json={'message': 'm', 'content': 'aGk=', 'branch': 'codebridge/test'}, headers=self.auth)
        self.assertEqual(res.status_code, 503)
        self.assertTrue(all(call[0] == 'GET' for call in _Client.calls))

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
