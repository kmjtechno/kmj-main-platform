"""Read-only VPS capacity and AI route diagnostics; never prints credentials."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path


def capacity_snapshot() -> dict:
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        parts = value.split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    free = values.get("MemFree", 0)
    disk = shutil.disk_usage(Path.cwd())
    cores = len(os.sched_getaffinity(0))
    load = os.getloadavg()
    gib = 1024 ** 3
    return {
        "cpu_available_cores": cores,
        "load_1m": round(load[0], 2),
        "load_per_core": round(load[0] / max(1, cores), 3),
        "memory_total_gib": round(total / gib, 2),
        "memory_available_gib": round(available / gib, 2),
        "memory_used_excluding_reclaimable_gib": round((total - available) / gib, 2),
        "memory_free_gib": round(free / gib, 2),
        "disk_free_gib": round(disk.free / gib, 2),
        "parallel_verification_lanes": 2,
        "max_open_safe_task_prs": 3,
    }


async def main() -> None:
    from controller.model_router import FreeCloudRouter

    status = await FreeCloudRouter().status()
    credential_names = {
        "9router": "KMJ_9ROUTER_API_KEY",
        **{name: provider[1] for name, provider in FreeCloudRouter.BUILTIN_PROVIDERS.items()},
    }
    credential_presence = {
        provider: bool(os.getenv(env, "").strip())
        for provider, env in credential_names.items()
    }
    result = {
        "capacity": capacity_snapshot(),
        "ai": {
            key: status[key] for key in (
                "configured_providers", "reachable_providers", "provider_errors",
                "eligible_verified_zero", "eligible_public_verified_zero",
                "eligible_confidential_verified_zero", "paid_fallback", "local_llm",
            )
        },
        "credential_present": credential_presence,
        "official_free_client": {
            "configured": os.getenv("KMJ_OPENCODE_FREE_ENABLED") == "true"
            and Path(os.getenv("KMJ_OPENCODE_BINARY", "")).is_file(),
            "model": "opencode/big-pickle",
            "verification": "fresh price check and zero-cost completion required per task",
        },
        "http_route_state": (
            "VERIFIED_FREE_CANDIDATES_AVAILABLE"
            if status["eligible_confidential_verified_zero"]
            else "NO_CONFIDENTIAL_FREE_ROUTE_AVAILABLE"
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    if "--capacity-only" in sys.argv:
        print(json.dumps(capacity_snapshot(), indent=2, sort_keys=True))
    else:
        asyncio.run(main())

