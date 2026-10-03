from __future__ import annotations

import os
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


if __name__ == "__main__":
    unittest.main()
