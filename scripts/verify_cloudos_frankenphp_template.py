"""Offline structural gate for CloudOS-managed, Nginx-free PHP web template.

This validates a candidate configuration, not a running HTTP/TLS route.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CADDYFILE = ROOT / "deploy" / "cloudos" / "frankenphp" / "Caddyfile.example"


def check_template(text: str) -> None:
    active = "\n".join(
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ).lower()
    for required in ("frankenphp", "admin off", "http://:8080", "root * /app/public", "php_server"):
        if required not in active:
            raise ValueError("CLOUDOS_FRANKENPHP_TEMPLATE_INCOMPLETE_" + required.replace(" ", "_"))
    for prohibited in ("nginx", "php_fastcgi", "php-fpm", "reverse_proxy"):
        if prohibited in active:
            raise ValueError("CLOUDOS_FRANKENPHP_TEMPLATE_FORBIDDEN_" + prohibited)


def main() -> None:
    check_template(CADDYFILE.read_text(encoding="utf-8"))
    print("KMJ CloudOS FrankenPHP config structural gate PASS (not live TLS/HTTP proof)")


if __name__ == "__main__":
    main()
