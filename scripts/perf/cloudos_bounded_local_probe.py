#!/usr/bin/env python3
"""Safety-bounded LOCAL-only staging latency sample, not a million-user load test.

Runs only against 127.0.0.1:8080 (a CloudOS staging FrankenPHP process).
Never probes public DNS or asks CloudOS to purchase/scale resources.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from math import ceil
import json
from time import monotonic

_ALLOWED_PATHS = frozenset({"/up", "/", "/products"})
_MAX_REQUESTS = 1000
_MAX_WORKERS = 16


def validate_args(requests: int, workers: int, path: str) -> None:
    if type(requests) is not int or not 1 <= requests <= _MAX_REQUESTS:
        raise ValueError("BOUNDED_PROBE_REQUEST_LIMIT")
    if type(workers) is not int or not 1 <= workers <= _MAX_WORKERS:
        raise ValueError("BOUNDED_PROBE_WORKER_LIMIT")
    if path not in _ALLOWED_PATHS:
        raise ValueError("STAGING_PATH_NOT_APPROVED")


def nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, ceil(len(ordered) * percentile) - 1)], 3)


def _one_request(path: str) -> tuple[bool, float]:
    conn = HTTPConnection("127.0.0.1", 8080, timeout=2.0)
    start = monotonic()
    try:
        conn.request("GET", path, headers={"Host": "staging.kmjtechno.com", "Accept": "text/html"})
        response = conn.getresponse()
        first_byte_ms = (monotonic() - start) * 1000.0
        response.read(32768)
        return 200 <= response.status < 400, first_byte_ms
    except (OSError, TimeoutError):
        return False, (monotonic() - start) * 1000.0
    finally:
        conn.close()


def probe(requests: int, workers: int, path: str) -> dict:
    validate_args(requests, workers, path)
    start = monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_one_request, (path for _ in range(requests))))
    elapsed = max(monotonic() - start, 1e-6)
    latencies = [ms for ok, ms in results if ok]
    ok_count = len(latencies)
    return {
        "scope": "cloudos_local_staging_bounded_probe_only",
        "production_load_test": False,
        "million_user_capacity_verified": False,
        "path": path,
        "requests": requests,
        "workers": workers,
        "success": ok_count,
        "errors": requests - ok_count,
        "observed_rps": round(requests / elapsed, 3),
        "ttfb_success_ms": {
            "p50": nearest_rank(latencies, .50),
            "p95": nearest_rank(latencies, .95),
            "p99": nearest_rank(latencies, .99),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-local-staging", action="store_true", help="Required explicit opt-in")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--path", default="/up")
    args = parser.parse_args()
    validate_args(args.requests, args.workers, args.path)
    if not args.execute_local_staging:
        parser.error("BLOCKED: add --execute-local-staging after verifying port 8080 is CloudOS staging")
    result = probe(args.requests, args.workers, args.path)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
