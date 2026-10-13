"""Gate: CloudOS must be Main Platform's final host with safe authority boundaries.

This validates only an architecture contract, not cloud deployment readiness.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "deployment" / "main-platform-cloudos-v1.json"


def verify_contract(data: dict) -> None:
    required_values = {
        "schema_version": 1,
        "contract_id": "kmj.main-platform.on-cloudos.v1",
        "decision_status": "owner_locked_target_not_live",
        "platform_repository": "kmjtechno/kmj-main-platform",
        "hosting_repository": "kmjtechno/kmj-cloudos",
    }
    for key, required in required_values.items():
        value = data.get(key)
        if type(value) is not type(required) or value != required:
            raise ValueError("CLOUDOS_HOSTING_CONTRACT_INVALID_" + key.upper())
    values = [
        ("roles", "commercial_authority", "kmj-main-platform"),
        ("roles", "hosting_runtime_and_fleet", "kmj-cloudos"),
        ("roles", "public_identity_and_entitlement_authority", "kmj-main-platform"),
        ("target", "public_hostname", "kmjtechno.com"),
        ("target", "application", "independent_cloudos_managed_linux_workload"),
        ("interfaces", "integration", "versioned_authenticated_apis_signed_contracts_events"),
        ("interfaces", "direct_cross_repo_database_access", False),
        ("interfaces", "shared_application_database", False),
        ("availability", "existing_workloads_continue_during_platform_outage", True),
        ("availability", "cloudos_runtime_boot_requires_live_platform", False),
        ("availability", "runtime_survives_cloudos_control_plane_restart", True),
        ("availability", "do_not_grant_perpetual_unlicensed_customer_workloads", True),
        ("availability", "platform_internal_bootstrap_workload_uses_explicit_scoped_policy", True),
        ("release_policy", "staging_cloudos_deployment_first", True),
        ("release_policy", "exact_immutable_artifact_and_source_sha_required", True),
        ("release_policy", "current_cloudos_applicable_release_gates_required", True),
        ("release_policy", "database_backup_restore_rehearsal_required", True),
        ("release_policy", "real_transactional_email_and_signed_link_smoke_required", True),
        ("release_policy", "control_plane_outage_and_recovery_drill_required", True),
        ("release_policy", "owner_approval_for_production_cutover_required", True),
        ("prohibitions", "legacy_staging_homepage_mirror", True),
        ("prohibitions", "cloudos_direct_query_of_platform_authority_database", True),
        ("prohibitions", "announcing_live_migration_without_delivery_evidence", True),
    ]
    for section, key, required in values:
        payload = data.get(section)
        value = payload.get(key) if isinstance(payload, dict) else None
        if type(value) is not type(required) or value != required:
            raise ValueError(f"CLOUDOS_HOSTING_CONTRACT_INVALID_{section.upper()}_{key.upper()}")
    processes = data.get("target", {}).get("application_processes")
    if not isinstance(processes, list) or not {"php_fpm_web", "queue_worker", "scheduler"} <= set(processes):
        raise ValueError("CLOUDOS_HOSTING_PROCESSES_MISSING")
    stateful = data.get("target", {}).get("stateful_dependencies")
    if not isinstance(stateful, list) or not {"isolated_postgresql", "off_node_backup"} <= set(stateful):
        raise ValueError("CLOUDOS_HOSTING_STORAGE_MISSING")


def main() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    verify_contract(data)
    print("KMJ CloudOS-hosted Main Platform architecture contract PASS (not live deployment proof)")


if __name__ == "__main__":
    main()
