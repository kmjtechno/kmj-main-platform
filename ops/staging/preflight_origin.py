#!/usr/bin/env python3
"""Read-only staging DNS/TLS preflight. Never changes infrastructure or secrets."""
import json
import socket
import ssl


STAGING = "staging.kmjtechno.com"
PRODUCTION = "kmjtechno.com"


def resolve_ips(host):
    return {record[4][0] for record in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}


def verify_tls(host):
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=10) as connection:
        with context.wrap_socket(connection, server_hostname=host) as tls:
            tls.getpeercert()


def inspect(resolver=resolve_ips, probe=verify_tls):
    """Return fixed reason codes without contacting production app endpoints."""
    issues = []
    try:
        stage_ips = set(resolver(STAGING))
        production_ips = set(resolver(PRODUCTION))
        if not stage_ips or not production_ips:
            issues.append("DNS_UNRESOLVED")
        elif stage_ips & production_ips:
            issues.append("STAGING_SHARES_PRODUCTION_IP")
    except (OSError, ValueError):
        issues.append("DNS_LOOKUP_FAILED")
    try:
        probe(STAGING)
    except (OSError, ssl.SSLError, ValueError):
        issues.append("STAGING_TLS_NOT_VERIFIED")
    return {
        "staging": STAGING,
        "production": PRODUCTION,
        "result": "FAIL" if issues else "PASS",
        "issues": issues,
        "scope": "dns_and_trusted_tls_only_not_application_or_database_isolation",
    }


if __name__ == "__main__":
    result = inspect()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["result"] == "PASS" else 2)
