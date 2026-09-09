from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import os
import time
import uuid
import yaml

app = FastAPI(title="KMJ Autonomous Dev Controller", version="0.1.0")
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "runtime.json"
MISSION = ROOT / "mission" / "main-platform.yaml"


class StartRequest(BaseModel):
    requested_by: str = "owner-mobile"
    dry_run: bool = True


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"status": "IDLE", "last_cycle": None, "last_checkpoint": None}


def save_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    data["last_checkpoint"] = int(time.time())
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": os.getenv("KMJ_MODE", "bootstrap"),
        "paid_fallback": "PROHIBITED",
        "cloud_nexus": "UNTOUCHED",
    }


@app.get("/status")
def status():
    return load_state()


@app.get("/mission")
def mission():
    return yaml.safe_load(MISSION.read_text(encoding="utf-8"))


@app.post("/start")
def start(req: StartRequest):
    if os.getenv("KMJ_PAID_FALLBACK", "prohibited").lower() != "prohibited":
        raise HTTPException(409, "PAID_FALLBACK_POLICY_VIOLATION")
    if os.getenv("KMJ_LOCAL_LLM", "prohibited").lower() != "prohibited":
        raise HTTPException(409, "LOCAL_LLM_POLICY_VIOLATION")

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
            "message": (
                "Bootstrap controller is ready. No AI call is made until a current "
                "verified-zero provider route is configured. NO_FREE_ROUTE_AVAILABLE "
                "is the safe default."
            ),
        }
    )
    save_state(state)
    return {"accepted": True, "cycle_id": cycle, "state": state}
