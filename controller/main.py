from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from pathlib import Path
import json
import os
import re
import secrets
import time
import uuid
from urllib.parse import quote

import httpx
import yaml

from controller.model_router import FreeCloudRouter, NoFreeRouteAvailable

app = FastAPI(title="KMJ Main Platform Autonomous Engineer", version="0.3.1")
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "runtime.json"
MISSION = ROOT / "mission" / "main-platform.yaml"
router = FreeCloudRouter()

HIGH_RISK_TERMS = (
    "production",
    "dns",
    "billing",
    "payment",
    "drop database",
    "delete database",
    "signing key",
    "private key",
    "legal",
)

SYSTEM_PROMPT = """You are the KMJ Main Platform Autonomous Engineer.
Work only on kmjtechno/kmj-main-platform. Keep KMJ Cloud Nexus untouched.
Primary critical path: Organization -> Product -> Entitlement -> signed sandbox license -> validation -> revocation.
Prefer minimal, testable, reversible changes. Diagnose before editing. Never claim a test passed without evidence.
Generative AI is cloud-only. Paid fallback is prohibited. Unknown cost is not free.
Production, DNS, billing, destructive database actions, signing keys and legal actions require explicit owner approval.
Return a concise execution plan with: objective, evidence needed, files/components, tests, risks, and next safe action.
"""


class StartRequest(BaseModel):
    requested_by: str = "owner-mobile"
    dry_run: bool = True


class RouteRequest(BaseModel):
    route: str = "coding"


class AgentTaskRequest(BaseModel):
    task: str
    route: str = "coding"


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"status": "IDLE", "last_cycle": None, "last_checkpoint": None}


def save_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    data["last_checkpoint"] = int(time.time())
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def require_control_token(authorization: str | None):
    expected = os.getenv("KMJ_CONTROL_TOKEN", "")
    if not expected:
        raise HTTPException(503, "CONTROL_TOKEN_NOT_CONFIGURED")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "CONTROL_AUTH_REQUIRED")
    provided = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(403, "CONTROL_AUTH_INVALID")


def codebridge_github_repositories() -> set[str]:
    configured = os.getenv("KMJ_CODEBRIDGE_GITHUB_REPOSITORIES", "")
    return {
        item.strip()
        for item in configured.split(",")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", item.strip())
    }


def require_codebridge_github_proxy_token(authorization: str | None) -> None:
    expected = os.getenv("KMJ_CODEBRIDGE_GITHUB_PROXY_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(503, "CODEBRIDGE_GITHUB_PROXY_NOT_CONFIGURED")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "CODEBRIDGE_GITHUB_PROXY_AUTH_REQUIRED")
    provided = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(403, "CODEBRIDGE_GITHUB_PROXY_AUTH_INVALID")


NUMBER = r"[1-9][0-9]{0,9}"
SHA40 = r"[a-fA-F0-9]{40}"
GIT_REF = r"[A-Za-z0-9._/-]{1,255}"
# Main Platform holds the GitHub credential and is the authority on which
# GitHub operations CodeBridge may perform. CodeBridge user permission
# (read/write) is already enforced by the gateway from Main Platform user
# introspection; this allowlist is the second, credential-side boundary.
CODEBRIDGE_GITHUB_RESPONSE_MAX_BYTES = 4 * 1024 * 1024


def _safe_ref(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(GIT_REF, value) is not None
        and ".." not in value
        and "//" not in value
        and not value.startswith("/")
        and not value.endswith(("/", ".lock"))
        and "@{" not in value
    )


def _per_page(query: dict[str, str], maximum: int) -> bool:
    value = query.get("per_page")
    return value is None or (
        re.fullmatch(r"[1-9][0-9]{0,2}", value) is not None and int(value) <= maximum
    )


def _safe_content_path(path: str) -> bool:
    if not path or len(path) > 1024 or path.startswith("/") or "\\" in path:
        return False
    if re.search(r"[\x00-\x1f\x7f]", path):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    # Workflow files can exfiltrate repository secrets; never write them
    # through the shared CodeBridge credential.
    return not path.lower().startswith(".github/workflows/")


def codebridge_github_route_allowed(method: str, suffix: str, query: dict[str, str]) -> bool:
    keys = set(query)
    if method == "GET":
        if suffix == "":
            return not query
        if suffix == "pulls":
            return (
                keys <= {"state", "per_page"}
                and query.get("state", "open") in {"open", "closed", "all"}
                and _per_page(query, 30)
            )
        if re.fullmatch(rf"pulls/{NUMBER}", suffix):
            return not query
        if re.fullmatch(rf"pulls/{NUMBER}/files", suffix):
            return keys <= {"per_page"} and query.get("per_page", "100") == "100"
        if re.fullmatch(rf"pulls/{NUMBER}/(reviews|comments)", suffix):
            return keys <= {"per_page"} and _per_page(query, 100)
        if re.fullmatch(rf"issues/{NUMBER}", suffix):
            return not query
        if re.fullmatch(rf"issues/{NUMBER}/comments", suffix):
            return keys <= {"per_page"} and _per_page(query, 100)
        if suffix == "commits":
            return (
                keys <= {"per_page", "sha"}
                and _per_page(query, 50)
                and ("sha" not in query or _safe_ref(query["sha"]))
            )
        if re.fullmatch(rf"commits/{SHA40}/check-runs", suffix):
            return keys <= {"per_page"} and query.get("per_page", "100") == "100"
        if suffix == "actions/runs":
            return (
                keys <= {"per_page", "branch", "head_sha"}
                and _per_page(query, 100)
                and ("branch" not in query or _safe_ref(query["branch"]))
                and (
                    "head_sha" not in query
                    or re.fullmatch(SHA40, query["head_sha"]) is not None
                )
            )
        if re.fullmatch(rf"actions/runs/{NUMBER}", suffix):
            return not query
        if re.fullmatch(rf"actions/runs/{NUMBER}/jobs", suffix):
            return keys <= {"per_page"} and query.get("per_page", "100") == "100"
        if re.fullmatch(rf"actions/jobs/{NUMBER}(/logs)?", suffix):
            return not query
        return False
    if query:
        return False
    if method == "POST":
        return (
            suffix in {"git/refs", "pulls", "issues"}
            or re.fullmatch(rf"issues/{NUMBER}/comments", suffix) is not None
            or re.fullmatch(rf"pulls/{NUMBER}/reviews", suffix) is not None
            or re.fullmatch(rf"pulls/{NUMBER}/comments/{NUMBER}/replies", suffix)
            is not None
        )
    if method == "PUT":
        if re.fullmatch(rf"pulls/{NUMBER}/merge", suffix):
            return True
        return suffix.startswith("contents/") and _safe_content_path(
            suffix.removeprefix("contents/")
        )
    if method == "PATCH":
        return re.fullmatch(rf"pulls/{NUMBER}", suffix) is not None
    return False


def _bounded_text(value: object, minimum: int, maximum: int) -> bool:
    return isinstance(value, str) and minimum <= len(value) <= maximum


def _invalid() -> HTTPException:
    return HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")


def validate_codebridge_github_write(suffix: str, payload: object, method: str = "POST") -> None:
    if not isinstance(payload, dict):
        raise _invalid()
    if method == "POST" and suffix == "git/refs":
        if set(payload) != {"ref", "sha"}:
            raise _invalid()
        ref = payload.get("ref")
        sha = payload.get("sha")
        if not isinstance(ref, str) or not ref.startswith("refs/heads/"):
            raise _invalid()
        if not _safe_ref(ref.removeprefix("refs/heads/")):
            raise _invalid()
        if not isinstance(sha, str) or not re.fullmatch(SHA40, sha):
            raise _invalid()
        return
    if method == "POST" and suffix == "pulls":
        if set(payload) - {"title", "body", "head", "base", "draft"}:
            raise _invalid()
        if not _bounded_text(payload.get("title"), 1, 256):
            raise _invalid()
        if not _bounded_text(payload.get("body", ""), 0, 20000):
            raise _invalid()
        for field in ("head", "base"):
            if not _safe_ref(payload.get(field)):
                raise _invalid()
        if "draft" in payload and not isinstance(payload["draft"], bool):
            raise _invalid()
        return
    if method == "POST" and suffix == "issues":
        if set(payload) - {"title", "body"} or not _bounded_text(payload.get("title"), 1, 256):
            raise _invalid()
        if not _bounded_text(payload.get("body", ""), 0, 20000):
            raise _invalid()
        return
    if method == "POST" and (
        re.fullmatch(rf"issues/{NUMBER}/comments", suffix)
        or re.fullmatch(rf"pulls/{NUMBER}/comments/{NUMBER}/replies", suffix)
    ):
        if set(payload) != {"body"} or not _bounded_text(payload["body"], 1, 20000):
            raise _invalid()
        return
    if method == "POST" and re.fullmatch(rf"pulls/{NUMBER}/reviews", suffix):
        if set(payload) - {"body", "event", "commit_id"}:
            raise _invalid()
        # Approval remains a human decision; never through the shared credential.
        if payload.get("event") not in {"COMMENT", "REQUEST_CHANGES"}:
            raise _invalid()
        if not _bounded_text(payload.get("body"), 1, 20000):
            raise _invalid()
        if "commit_id" in payload and not (
            isinstance(payload["commit_id"], str)
            and re.fullmatch(SHA40, payload["commit_id"])
        ):
            raise _invalid()
        return
    if method == "PUT" and re.fullmatch(rf"pulls/{NUMBER}/merge", suffix):
        if set(payload) != {"sha", "merge_method"}:
            raise _invalid()
        if not isinstance(payload["sha"], str) or not re.fullmatch(SHA40, payload["sha"]):
            raise _invalid()
        if payload["merge_method"] not in {"squash", "merge", "rebase"}:
            raise _invalid()
        return
    if method == "PUT" and suffix.startswith("contents/"):
        if not _safe_content_path(suffix.removeprefix("contents/")):
            raise HTTPException(405, "CODEBRIDGE_GITHUB_ROUTE_DENIED")
        allowed = {"message", "content", "branch", "sha"}
        if set(payload) - allowed or not {"message", "content", "branch"} <= set(payload):
            raise _invalid()
        if not _bounded_text(payload["message"], 1, 256):
            raise _invalid()
        if not _bounded_text(payload["content"], 0, 360000):
            raise _invalid()
        if not re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", payload["content"]):
            raise _invalid()
        if not _safe_ref(payload["branch"]):
            raise _invalid()
        if "sha" in payload and not (
            isinstance(payload["sha"], str) and re.fullmatch(SHA40, payload["sha"])
        ):
            raise _invalid()
        return
    if method == "PATCH" and re.fullmatch(rf"pulls/{NUMBER}", suffix):
        if not payload or set(payload) - {"title", "body", "base", "state"}:
            raise _invalid()
        if "title" in payload and not _bounded_text(payload["title"], 1, 256):
            raise _invalid()
        if "body" in payload and not _bounded_text(payload["body"], 0, 20000):
            raise _invalid()
        if "base" in payload and not _safe_ref(payload["base"]):
            raise _invalid()
        if "state" in payload and payload["state"] not in {"open", "closed"}:
            raise _invalid()
        return
    raise HTTPException(405, "CODEBRIDGE_GITHUB_ROUTE_DENIED")


def high_risk_reason(task: str) -> str | None:
    task_l = task.lower()
    for term in HIGH_RISK_TERMS:
        if term in task_l:
            return term
    return None


@app.get("/")
def root():
    return {
        "service": "KMJ Main Platform Autonomous Engineer",
        "version": "0.3.1",
        "health": "/health",
        "router_status": "/router/status",
        "agent_plan": "/agent/plan",
        "cloud_nexus": "UNTOUCHED",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": os.getenv("KMJ_MODE", "bootstrap"),
        "router": "KMJ federated verified-zero cloud router",
        "paid_fallback": "PROHIBITED",
        "unknown_cost_is_free": False,
        "local_llm": "PROHIBITED",
        "cloud_nexus": "UNTOUCHED",
        "write_control": "TOKEN_GATED" if os.getenv("KMJ_CONTROL_TOKEN") else "DISABLED",
        "execution_enabled": os.getenv("KMJ_EXECUTION_ENABLED", "false").lower() == "true",
        "autonomy_level": "execution-gated" if os.getenv("KMJ_EXECUTION_ENABLED", "false").lower() == "true" else "planning-only",
        "router_timeout_seconds": router.timeout,
        "codebridge_github_proxy": (
            len(os.getenv("KMJ_CODEBRIDGE_GITHUB_PROXY_TOKEN", "")) >= 32
            and bool(os.getenv("GITHUB_TOKEN", ""))
            and bool(codebridge_github_repositories())
        ),
    }


@app.api_route(
    "/codebridge/github/repos/{owner}/{repo}",
    methods=["GET"],
)
@app.api_route(
    "/codebridge/github/repos/{owner}/{repo}/{suffix:path}",
    methods=["GET", "POST", "PUT", "PATCH"],
)
async def codebridge_github_proxy(
    owner: str,
    repo: str,
    request: Request,
    suffix: str = "",
    authorization: str | None = Header(default=None),
):
    require_codebridge_github_proxy_token(authorization)
    repository = f"{owner}/{repo}"
    if repository not in codebridge_github_repositories():
        raise HTTPException(404, "CODEBRIDGE_GITHUB_REPOSITORY_DENIED")

    query = {key: value for key, value in request.query_params.items()}
    if not codebridge_github_route_allowed(request.method, suffix, query):
        raise HTTPException(405, "CODEBRIDGE_GITHUB_ROUTE_DENIED")

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        raise HTTPException(503, "GITHUB_TOKEN_NOT_CONFIGURED")

    body: bytes | None = None
    if request.method in {"POST", "PUT", "PATCH"}:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID") from exc
        validate_codebridge_github_write(suffix, payload, request.method)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    path = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
    if suffix:
        path += "/" + quote(suffix, safe="/")
    url = "https://api.github.com" + path
    if request.url.query:
        url += "?" + request.url.query

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "KMJ-CodeBridge-GitHub-Proxy/1",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )

    if len(upstream.content) > CODEBRIDGE_GITHUB_RESPONSE_MAX_BYTES:
        raise HTTPException(413, "CODEBRIDGE_GITHUB_RESPONSE_TOO_LARGE")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/status")
def status():
    return load_state()


@app.get("/mission")
def mission():
    return yaml.safe_load(MISSION.read_text(encoding="utf-8"))


@app.get("/router/status")
async def router_status():
    return await router.status()


@app.post("/router/select")
async def router_select(req: RouteRequest, authorization: str | None = Header(default=None)):
    require_control_token(authorization)
    try:
        candidate = await router.select(req.route)
    except NoFreeRouteAvailable:
        raise HTTPException(503, "NO_FREE_ROUTE_AVAILABLE")
    return {
        "route": req.route,
        "model": candidate.model_id,
        "provider": candidate.provider,
        "owner": candidate.owner,
        "verification": candidate.reason,
        "paid_fallback": "PROHIBITED",
    }


@app.post("/agent/plan")
async def agent_plan(req: AgentTaskRequest, authorization: str | None = Header(default=None)):
    require_control_token(authorization)
    risk = high_risk_reason(req.task)
    if risk:
        return {
            "accepted": False,
            "status": "OWNER_APPROVAL_REQUIRED",
            "risk": risk,
            "task": req.task,
        }

    try:
        result = await router.complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": req.task},
            ],
            route=req.route,
        )
    except NoFreeRouteAvailable as exc:
        raise HTTPException(503, str(exc))

    return {
        "accepted": True,
        "task": req.task,
        "route": req.route,
        "model": result["model"],
        "provider": result.get("provider"),
        "verification": result["verification"],
        "attempts": result["attempts"],
        "response": result["response"],
    }


@app.post("/start")
def start(req: StartRequest, authorization: str | None = Header(default=None)):
    require_control_token(authorization)

    if os.getenv("KMJ_PAID_FALLBACK", "prohibited").lower() != "prohibited":
        raise HTTPException(409, "PAID_FALLBACK_POLICY_VIOLATION")
    if os.getenv("KMJ_LOCAL_LLM", "prohibited").lower() != "prohibited":
        raise HTTPException(409, "LOCAL_LLM_POLICY_VIOLATION")
    if not req.dry_run and os.getenv("KMJ_EXECUTION_ENABLED", "false").lower() != "true":
        raise HTTPException(423, "AUTONOMOUS_EXECUTION_LOCKED")

    state = load_state()
    if state.get("status") == "RUNNING":
        return {"accepted": False, "reason": "CYCLE_ALREADY_RUNNING", "state": state}

    cycle = str(uuid.uuid4())
    state.update(
        {
            "status": "CHECKPOINTED",
            "last_cycle": cycle,
            "requested_by": req.requested_by,
            "dry_run": req.dry_run,
            "agent": "KMJ Main Platform Autonomous Engineer",
            "router": "KMJ federated verified-zero cloud router",
            "message": (
                "Agent runtime is ready for verified-free cloud planning and failover. "
                "Autonomous repository writes remain separately execution-gated."
            ),
        }
    )
    save_state(state)
    return {"accepted": True, "cycle_id": cycle, "state": state}
