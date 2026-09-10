from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import os
import secrets
import time
import uuid
import yaml

from controller.model_router import FreeCloudRouter, NoFreeRouteAvailable

app = FastAPI(title="KMJ Main Platform Autonomous Engineer", version="0.2.0")
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "runtime.json"
MISSION = ROOT / "mission" / "main-platform.yaml"
router = FreeCloudRouter()


class StartRequest(BaseModel):
    requested_by: str = "owner-mobile"
    dry_run: bool = True


class RouteRequest(BaseModel):
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


@app.get("/")
def root():
    return {
        "service": "KMJ Main Platform Autonomous Engineer",
        "version": "0.2.0",
        "health": "/health",
        "router_status": "/router/status",
        "cloud_nexus": "UNTOUCHED",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": os.getenv("KMJ_MODE", "bootstrap"),
        "router": "9Router + KMJ strict verified-zero gate",
        "paid_fallback": "PROHIBITED",
        "unknown_cost_is_free": False,
        "local_llm": "PROHIBITED",
        "cloud_nexus": "UNTOUCHED",
        "write_control": "TOKEN_GATED" if os.getenv("KMJ_CONTROL_TOKEN") else "DISABLED",
        "execution_enabled": os.getenv("KMJ_EXECUTION_ENABLED", "false").lower() == "true",
    }


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
        "owner": candidate.owner,
        "verification": candidate.reason,
        "paid_fallback": "PROHIBITED",
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
            "router": "9Router + verified-zero gate",
            "message": (
                "Agent controller is ready. AI work can route only through dynamically "
                "discovered verified-zero cloud models. Unknown-cost or paid models are "
                "rejected. NO_FREE_ROUTE_AVAILABLE is the safe default."
            ),
        }
    )
    save_state(state)
    return {"accepted": True, "cycle_id": cycle, "state": state}
