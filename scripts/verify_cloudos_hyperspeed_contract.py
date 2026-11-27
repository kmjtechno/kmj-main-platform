"""Read-only CloudOS Main Platform HyperSpeed policy guard, NOT benchmark proof."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "contracts" / "performance" / "main-platform-hyperspeed-v1.json"


def verify(data: dict) -> None:
    if data.get("schema_version") != 1 or data.get("contract_id") != "kmj.main-platform.hyperspeed.v1":
        raise ValueError("HYPERSPEED_CONTRACT_VERSION_MISMATCH")
    if data.get("decision") != "cloudos_managed_hyperspeed_target_not_measured":
        raise ValueError("HYPERSPEED_MUST_NOT_CLAIM_PROVEN")
    required_true = {
        "goals": ["no_unconditional_zero_latency_guarantee", "performance_defined_by_measured_latency_throughput_and_cost"],
        "traffic_isolation": ["cache_key_must_not_include_secrets", "avoid_app_or_db_for_edge_cache_hits"],
        "cloudos_runtime": ["stateless_replicas", "multi_node_anti_affinity_required", "private_upstreams_only", "tls_between_nodes_required",
                            "ingress_route_change_requires_live_probe", "bounded_request_and_queue_concurrency", "no_public_direct_app_listener"],
        "capacity_control": ["rps_per_replica_from_real_benchmark_only", "scale_by_observed_latency_error_cpu_memory_queue_depth",
                             "max_replicas_requires_approved_finite_cost_and_resources", "no_paid_or_burst_capacity_auto_purchase",
                             "scale_down_waits_for_drain", "insufficient_capacity_fails_closed_with_retry_after",
                             "cost_free_hardware_does_not_imply_unlimited_capacity"],
        "data_and_resilience": ["shared_redis_valkey_for_sessions_cache_rate_limiter", "database_pool_budget_and_connection_pressure_gates",
                                "no_full_table_scan_for_public_homepage", "analytics_search_ai_emails_and_webhooks_async_when_safe",
                                "outbox_idempotency_for_payments_and_entitlements", "off_node_backup_and_restore_drill",
                                "control_plane_outage_existing_workload_survives"],
        "qualification": ["targets_not_achieved_results", "require_real_staging_distributed_load_and_evidence",
                          "no_load_on_production_without_scoped_approved_window", "unproven_claims_must_stay_blocked"],
    }
    for section, keys in required_true.items():
        payload = data.get(section)
        if not isinstance(payload, dict):
            raise ValueError("HYPERSPEED_MISSING_" + section.upper())
        for key in keys:
            if payload.get(key) is not True:
                raise ValueError(f"HYPERSPEED_GUARD_{section.upper()}_{key.upper()}")
    runtime = data.get("cloudos_runtime")
    if (runtime.get("ingress"), runtime.get("web"), runtime.get("health_check_path")) != (
        "caddy_non_nginx", "frankenphp_classic", "/up"
    ):
        raise ValueError("HYPERSPEED_RUNTIME_INVALID")
    if type(runtime.get("minimum_production_replicas")) is not int or runtime["minimum_production_replicas"] < 2:
        raise ValueError("HYPERSPEED_HA_REPLICA_FLOOR")
    traffic = data["traffic_isolation"]
    if traffic.get("identity_payments_licenses_admin") != "private_no_store_never_shared_edge_cached":
        raise ValueError("HYPERSPEED_PRIVATE_CACHE_ISOLATION")
    if traffic.get("writes") != "idempotent_scoped_backpressure_non_replay":
        raise ValueError("HYPERSPEED_NONREPLAY_WRITES")
    cap = data["capacity_control"]
    util = cap.get("headroom_fraction")
    if type(util) not in (float, int) or not 0 < util <= 0.75:
        raise ValueError("HYPERSPEED_UNSAFE_CAPACITY_HEADROOM")
    slo = data["qualification"].get("slo_targets")
    if not isinstance(slo, dict) or not 0 < slo.get("monthly_availability_percent", 0) < 100:
        raise ValueError("HYPERSPEED_SLO_INVALID")
    if not isinstance(data["qualification"].get("required_evidence"), list) or len(data["qualification"]["required_evidence"]) < 8:
        raise ValueError("HYPERSPEED_EVIDENCE_INCOMPLETE")


def main() -> None:
    verify(json.loads(PATH.read_text(encoding="utf-8")))
    print("HYPERSPEED_POLICY_PASS (architecture only; no live load test)")


if __name__ == "__main__":
    main()
