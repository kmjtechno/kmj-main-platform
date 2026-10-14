"""Offline structural gate for CloudOS-managed, Nginx-free PHP web template.

This validates a candidate configuration, not a running HTTP/TLS route.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CADDYFILE = ROOT / "deploy" / "cloudos" / "frankenphp" / "Caddyfile.example"
RUNTIME_ENV = ROOT / "deploy" / "cloudos" / "frankenphp" / "runtime.env.example"


def check_template(text: str) -> None:
    active = "\n".join(
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ).lower()
    for required in ("frankenphp", "admin off", "http://:8080", "root * /app/public", "php_server"):
        if required not in active:
            raise ValueError("CLOUDOS_FRANKENPHP_TEMPLATE_INCOMPLETE_" + required.replace(" ", "_"))
    if "path /build/assets/*" not in active or "max-age=31536000, immutable" not in active:
        raise ValueError("CLOUDOS_VERSIONED_ASSET_CACHE_MISSING")
    if "cache-control" in active and "path /build/assets/*" not in active:
        raise ValueError("CLOUDOS_UNSAFE_PUBLIC_CACHE")
    for prohibited in ("nginx", "php_fastcgi", "php-fpm", "reverse_proxy"):
        if prohibited in active:
            raise ValueError("CLOUDOS_FRANKENPHP_TEMPLATE_FORBIDDEN_" + prohibited)


def main() -> None:
    check_template(CADDYFILE.read_text(encoding="utf-8"))
    values = {}
    for line in RUNTIME_ENV.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("CLOUDOS_ENV_INVALID")
        key, value = line.split("=", 1)
        values[key] = value
    expected = {
        "APP_ENV": "production", "APP_DEBUG": "false",
        "CACHE_STORE": "redis", "SESSION_DRIVER": "redis",
        "QUEUE_CONNECTION": "redis",
    }
    for key, required in expected.items():
        if values.get(key) != required:
            raise ValueError("CLOUDOS_RUNTIME_REDIS_REQUIRED_" + key)
    if any("PASSWORD" in key or key in {"APP_KEY", "MAIL_PASSWORD"} for key in values):
        raise ValueError("CLOUDOS_RUNTIME_SECRETS_FORBIDDEN")
    print("KMJ CloudOS FrankenPHP config structural gate PASS (not live TLS/HTTP proof)")


if __name__ == "__main__":
    main()
