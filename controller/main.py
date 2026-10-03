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


def codebridge_github_route_allowed(method: str, suffix: str, query: dict[str, str]) -> bool:
    if method == "GET":
        if suffix == "":
            return not query
        if re.fullmatch(r"pulls/[1-9][0-9]*", suffix):
            return not query
        if re.fullmatch(r"pulls/[1-9][0-9]*/files", suffix):
            return set(query) <= {"per_page"} and query.get("per_page", "100") == "100"
        if suffix == "actions/runs":
            return set(query) <= {"per_page", "branch"}
        if re.fullmatch(r"actions/runs/[1-9][0-9]*/jobs", suffix):
            return set(query) <= {"per_page"} and query.get("per_page", "100") == "100"
        if re.fullmatch(r"actions/jobs/[1-9][0-9]*/logs", suffix):
            return not query
        return False
    if method == "POST":
        return suffix in {"git/refs", "pulls"} and not query
    return False


def validate_codebridge_github_write(suffix: str, payload: object) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
    if suffix == "git/refs":
        if set(payload) != {"ref", "sha"}:
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        ref = payload.get("ref")
        sha = payload.get("sha")
        if not isinstance(ref, str) or not re.fullmatch(r"refs/heads/[A-Za-z0-9._/-]{1,255}", ref):
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", sha):
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        return
    if suffix == "pulls":
        if set(payload) - {"title", "body", "head", "base", "draft"}:
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        if not isinstance(payload.get("title"), str) or not 1 <= len(payload["title"]) <= 256:
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        if not isinstance(payload.get("body", ""), str) or len(payload.get("body", "")) > 20000:
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        for field in ("head", "base"):
            value = payload.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,255}", value):
                raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
        if "draft" in payload and not isinstance(payload["draft"], bool):
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID")
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
    methods=["GET", "POST"],
)
@app.api_route(
    "/codebridge/github/repos/{owner}/{repo}/{suffix:path}",
    methods=["GET", "POST"],
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
    if request.method == "POST":
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(400, "CODEBRIDGE_GITHUB_BODY_INVALID") from exc
        validate_codebridge_github_write(suffix, payload)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    path = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
    if suffix:
        path += "/" + suffix
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

    if len(upstream.content) > 524288:
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
