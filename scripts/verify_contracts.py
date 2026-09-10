from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "packages" / "contracts" / "openapi" / "v1" / "main-platform.yaml"
EVENTS = ROOT / "packages" / "contracts" / "events" / "v1"

REQUIRED_SCHEMAS = {
    "Organization",
    "Product",
    "Entitlement",
    "SignedLicenseEnvelope",
    "LicenseValidationResult",
    "LicenseRevocation",
    "Release",
    "ErrorResponse",
}

REQUIRED_PATHS = {
    "/v1/organizations",
    "/v1/products",
    "/v1/entitlements",
    "/v1/licenses/sandbox",
    "/v1/licenses/validate",
    "/v1/licenses/{licenseId}/revoke",
    "/v1/releases/{releaseId}",
}

FORBIDDEN_TOKENS = {
    "private_key",
    "privateKey",
    "card_number",
    "cardNumber",
    "password_hash",
    "database_row",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_no_forbidden_tokens(obj: object, *, where: str) -> None:
    serialized = json.dumps(obj, sort_keys=True)
    found = sorted(token for token in FORBIDDEN_TOKENS if token in serialized)
    if found:
        raise AssertionError(f"{where}: forbidden contract tokens found: {found}")


def verify_openapi() -> None:
    spec = load_yaml(OPENAPI)
    assert spec.get("openapi") == "3.1.0", "OpenAPI must be 3.1.0"
    assert spec.get("x-kmj-contract-version") == 1, "Contract version must be 1"

    paths = set((spec.get("paths") or {}).keys())
    missing_paths = REQUIRED_PATHS - paths
    assert not missing_paths, f"Missing required paths: {sorted(missing_paths)}"

    schemas = set((((spec.get("components") or {}).get("schemas")) or {}).keys())
    missing_schemas = REQUIRED_SCHEMAS - schemas
    assert not missing_schemas, f"Missing required schemas: {sorted(missing_schemas)}"

    issue_request = spec["components"]["schemas"]["IssueEntitlementRequest"]
    required = set(issue_request.get("required") or [])
    assert "policy_decision_id" in required, "Entitlements must require explicit policy authority"

    license_request = spec["components"]["schemas"]["IssueSandboxLicenseRequest"]
    required = set(license_request.get("required") or [])
    assert "entitlement_id" in required, "License issuance must derive from entitlement authority"

    release = spec["components"]["schemas"]["Release"]
    release_required = set(release.get("required") or [])
    assert {"artifact_digest", "provenance_ref"}.issubset(release_required), (
        "Trusted release contract must require digest and provenance"
    )

    assert_no_forbidden_tokens(spec, where="OpenAPI")


def verify_event(path: Path, expected_type: str) -> None:
    schema = load_json(path)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    all_of = schema.get("allOf") or []
    assert all_of and all_of[0].get("$ref") == "./envelope.schema.json"
    typed = all_of[1]["properties"]["type"]["const"]
    assert typed == expected_type
    assert_no_forbidden_tokens(schema, where=path.name)


def verify_envelope() -> None:
    envelope = load_json(EVENTS / "envelope.schema.json")
    assert envelope["properties"]["specversion"]["const"] == "1.0"
    required = set(envelope.get("required") or [])
    assert {"id", "source", "type", "time", "subject", "data"}.issubset(required)
    pattern = envelope["properties"]["type"]["pattern"]
    assert "mainplatform" in pattern
    assert_no_forbidden_tokens(envelope, where="event envelope")


def main() -> None:
    verify_openapi()
    verify_envelope()
    verify_event(
        EVENTS / "entitlement.issued.schema.json",
        "com.kmjtechno.mainplatform.v1.entitlement.issued",
    )
    verify_event(
        EVENTS / "license.revoked.schema.json",
        "com.kmjtechno.mainplatform.v1.license.revoked",
    )
    print("KMJ contracts v1 verification PASS")


if __name__ == "__main__":
    main()
