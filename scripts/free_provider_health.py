from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from controller.model_router import FreeCloudRouter


def build_snapshot(router_status: dict) -> dict:
    configured = list(router_status.get("configured_providers", []))
    reachable = list(router_status.get("reachable_providers", []))
    eligible = int(router_status.get("eligible_verified_zero", 0))
    errors = dict(router_status.get("provider_errors", {}))

    opencode_binary = os.getenv("KMJ_OPENCODE_BINARY", "").strip()
    opencode_ready = (
        os.getenv("KMJ_OPENCODE_FREE_ENABLED", "").strip().lower() == "true"
        and bool(opencode_binary)
        and Path(opencode_binary).is_file()
    )

    if eligible > 0:
        status = "healthy"
    elif reachable or opencode_ready:
        status = "degraded"
    else:
        status = "dormant"

    return {
        "schema": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "configured_providers": configured,
        "reachable_providers": reachable,
        "provider_errors": errors,
        "eligible_verified_zero": eligible,
        "eligible_confidential_verified_zero": int(
            router_status.get("eligible_confidential_verified_zero", 0)
        ),
        "rejected_unknown_or_paid": int(
            router_status.get("rejected_unknown_or_paid", 0)
        ),
        "opencode_client_ready": opencode_ready,
        "paid_fallback": "PROHIBITED",
        "unknown_cost_is_free": False,
        "local_llm": "PROHIBITED",
    }


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


async def run(output: Path) -> dict:
    router = FreeCloudRouter()
    snapshot = build_snapshot(await router.status())
    atomic_write(output, snapshot)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=os.getenv(
            "KMJ_FREE_PROVIDER_HEALTH_PATH",
            "/home/info/.kmj/free-provider-health.json",
        ),
    )
    args = parser.parse_args()
    snapshot = asyncio.run(run(Path(args.output)))
    print(json.dumps(snapshot, separators=(",", ":"), sort_keys=True))
    return 0 if snapshot["status"] in {"healthy", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
