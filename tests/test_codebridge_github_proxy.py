from __future__ import annotations

import os
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from controller.main import (
    codebridge_github_repositories,
    codebridge_github_route_allowed,
    require_codebridge_github_proxy_token,
    validate_codebridge_github_write,
)


class CodeBridgeGitHubProxyTest(unittest.TestCase):
    def setUp(self) -> None:
        env = patch.dict(os.environ, {'KMJ_CODEBRIDGE_GITHUB_WRITE_BRANCHES': json.dumps({'kmjtechno/kmj-codebridge': ['codebridge/test', 'codebridge/x']})})
        env.start()
        self.addCleanup(env.stop)

    def test_repository_allowlist_is_explicit_and_sanitized(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KMJ_CODEBRIDGE_GITHUB_REPOSITORIES":
                    "kmjtechno/kmj-codebridge, kmjtechno/kmj-main-platform, bad repo"
            },
            clear=False,
        ):
            self.assertEqual(
                codebridge_github_repositories(),
                {
                    "kmjtechno/kmj-codebridge",
                    "kmjtechno/kmj-main-platform",
                },
            )

    def test_proxy_token_is_required_and_constant_time_checked(self) -> None:
        secret = "x" * 48
        with patch.dict(
            os.environ,
            {"KMJ_CODEBRIDGE_GITHUB_PROXY_TOKEN": secret},
            clear=False,
        ):
            require_codebridge_github_proxy_token(f"Bearer {secret}")
            with self.assertRaises(HTTPException) as denied:
                require_codebridge_github_proxy_token("Bearer wrong")
            self.assertEqual(denied.exception.status_code, 403)

    def test_only_required_codebridge_github_routes_are_allowed(self) -> None:
        self.assertTrue(codebridge_github_route_allowed("GET", "", {}))
        self.assertTrue(
            codebridge_github_route_allowed(
                "GET", "pulls/42/files", {"per_page": "100"}
            )
        )
        self.assertTrue(
            codebridge_github_route_allowed(
                "GET", "actions/runs", {"per_page": "20", "branch": "main"}
            )
        )
        self.assertTrue(codebridge_github_route_allowed("POST", "git/refs", {}))
        self.assertTrue(codebridge_github_route_allowed("POST", "pulls", {}))
        self.assertFalse(codebridge_github_route_allowed("DELETE", "git/refs/x", {}))
        self.assertFalse(codebridge_github_route_allowed("GET", "contents/.env", {}))
        self.assertFalse(codebridge_github_route_allowed("GET", "actions/secrets", {}))

    def test_branch_and_pull_request_bodies_are_bounded(self) -> None:
        validate_codebridge_github_write(
            "git/refs",
            {"ref": "refs/heads/codebridge/test", "sha": "a" * 40},
            repository="kmjtechno/kmj-codebridge",
        )
        validate_codebridge_github_write(
            "pulls",
            {
                "title": "CodeBridge test",
                "body": "",
                "head": "codebridge/test",
                "base": "main",
                "draft": False,
            },
        )
        with self.assertRaises(HTTPException):
            validate_codebridge_github_write(
                "git/refs",
                {"ref": "refs/heads/../unsafe", "sha": "a" * 40},
            )
        with self.assertRaises(HTTPException):
            validate_codebridge_github_write(
                "pulls",
                {
                    "title": "x",
                    "body": "",
                    "head": "feature",
                    "base": "main",
                    "draft": False,
                    "extra": "not allowed",
                },
            )

    def test_every_codebridge_github_tool_route_is_covered(self) -> None:
        sha = "a" * 40
        allowed = [
            ("GET", "pulls", {"state": "open", "per_page": "30"}),
            ("GET", "pulls/7", {}),
            ("GET", "pulls/7/reviews", {"per_page": "20"}),
            ("GET", "pulls/7/comments", {"per_page": "20"}),
            ("GET", "issues/7", {}),
            ("GET", "issues/7/comments", {"per_page": "50"}),
            ("GET", "commits", {"per_page": "20", "sha": "main"}),
            ("GET", f"commits/{sha}/check-runs", {"per_page": "100"}),
            ("GET", "actions/runs", {"head_sha": sha, "per_page": "100"}),
            ("GET", "actions/runs/99", {}),
            ("GET", "actions/runs/99/jobs", {"per_page": "100"}),
            ("GET", "actions/jobs/99", {}),
            ("GET", "actions/jobs/99/logs", {}),
            ("POST", "issues", {}),
            ("POST", "issues/7/comments", {}),
            ("POST", "pulls/7/reviews", {}),
            ("POST", "pulls/7/comments/55/replies", {}),
            ("PUT", "contents/src/app.js", {}),
            ("PATCH", "pulls/7", {}),
        ]
        for method, suffix, query in allowed:
            with self.subTest(method=method, suffix=suffix):
                self.assertTrue(codebridge_github_route_allowed(method, suffix, query))

    def test_unsafe_routes_and_queries_are_denied(self) -> None:
        denied = [
            ("GET", "pulls", {"per_page": "31"}),
            ("GET", "pulls", {"state": "draft"}),
            ("GET", "commits", {"sha": "../x"}),
            ("GET", "actions/runs", {"head_sha": "not-a-sha"}),
            ("GET", "actions/runs", {"actor": "x"}),
            ("GET", "pulls/0", {}),
            ("PUT", "contents/../etc/passwd", {}),
            ("PUT", "contents/.github/workflows/ci.yml", {}),
            ("PUT", "contents/.GitHub/Workflows/x.yml", {}),
            ("PUT", "contents/", {}),
            ("PATCH", "issues/7", {}),
            ("POST", "pulls/7/merge", {}),
            ("PUT", "pulls/7/merge", {"x": "1"}),
            ("DELETE", "pulls/7", {}),
            ("POST", "actions/runs/9/rerun", {}),
            ("PUT", "collaborators/someone", {}),
        ]
        for method, suffix, query in denied:
            with self.subTest(method=method, suffix=suffix, query=query):
                self.assertFalse(codebridge_github_route_allowed(method, suffix, query))

    def test_reviews_can_never_approve_and_merge_requires_exact_sha(self) -> None:
        validate_codebridge_github_write(
            "pulls/7/reviews", {"event": "COMMENT", "body": "ok"}, "POST"
        )
        for event in ("APPROVE", "approve", None):
            with self.subTest(event=event):
                with self.assertRaises(HTTPException):
                    validate_codebridge_github_write(
                        "pulls/7/reviews", {"event": event, "body": "x"}, "POST"
                    )
        self.assertFalse(codebridge_github_route_allowed("PUT", "pulls/7/merge", {}))
        with self.assertRaises(HTTPException):
            validate_codebridge_github_write(
                "pulls/7/merge", {"sha": "b" * 40, "merge_method": "squash"}, "PUT"
            )
        for body in (
            {"merge_method": "squash"},
            {"sha": "short", "merge_method": "squash"},
            {"sha": "b" * 40, "merge_method": "octopus"},
            {"sha": "b" * 40, "merge_method": "squash", "commit_title": "x"},
        ):
            with self.subTest(body=body):
                with self.assertRaises(HTTPException):
                    validate_codebridge_github_write("pulls/7/merge", body, "PUT")

    def test_contents_issue_comment_and_patch_bodies_are_bounded(self) -> None:
        validate_codebridge_github_write(
            "contents/src/a.js",
            {"message": "m", "content": "aGk=", "branch": "codebridge/x", "sha": "c" * 40},
            "PUT",
            repository="kmjtechno/kmj-codebridge",
        )
        for body in (
            {"message": "m", "content": "not base64!", "branch": "feature/x"},
            {"message": "m", "content": "aGk=", "branch": "../main"},
            {"message": "m", "content": "aGk=", "branch": "x", "committer": {}},
            {"content": "aGk=", "branch": "x"},
        ):
            with self.subTest(body=body):
                with self.assertRaises(HTTPException):
                    validate_codebridge_github_write("contents/src/a.js", body, "PUT")
        with self.assertRaises(HTTPException) as workflow:
            validate_codebridge_github_write(
                "contents/.github/workflows/x.yml",
                {"message": "m", "content": "aGk=", "branch": "x"},
                "PUT",
            )
        self.assertEqual(workflow.exception.status_code, 405)
        validate_codebridge_github_write("issues", {"title": "t", "body": "b"}, "POST")
        validate_codebridge_github_write("issues/7/comments", {"body": "b"}, "POST")
        with self.assertRaises(HTTPException):
            validate_codebridge_github_write("issues/7/comments", {"body": ""}, "POST")
        validate_codebridge_github_write("pulls/7", {"state": "closed"}, "PATCH")
        for body in ({}, {"state": "merged"}, {"draft": True}, {"base": "a..b"}):
            with self.subTest(body=body):
                with self.assertRaises(HTTPException):
                    validate_codebridge_github_write("pulls/7", body, "PATCH")


if __name__ == "__main__":
    unittest.main()
