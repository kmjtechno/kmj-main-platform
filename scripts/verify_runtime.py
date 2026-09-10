from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "apps" / "platform"
SOURCE = ROOT / "bootstrap" / "runtime-source.yaml"
EXPECTED_UPSTREAM = "87cce8705d712629ebddd70ccfbb06592ecbaac2"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    require(source["source_commit"] == EXPECTED_UPSTREAM, "Unexpected runtime upstream pin")
    require(source["runtime_target"]["laravel"] == 13, "Laravel target must be 13")
    require(str(source["runtime_target"]["php"]) == "8.5", "PHP target must be 8.5")
    require(source["runtime_target"]["inertia"] == 3, "Inertia target must be 3")
    require(source["runtime_target"]["react"] == 19, "React target must be 19")
    require(source["runtime_target"]["postgres"] == 18, "PostgreSQL target must be 18")

    required_files = [
        "artisan",
        "composer.json",
        "package.json",
        ".env.example",
        ".php-version",
        "UPSTREAM.md",
        "KMJ_BOUNDARY.md",
        "phpunit.xml",
    ]
    for rel in required_files:
        require((PLATFORM / rel).is_file(), f"Missing platform runtime file: {rel}")

    composer = json.loads((PLATFORM / "composer.json").read_text(encoding="utf-8"))
    require(composer["name"] == "kmjtechno/kmj-main-platform", "Composer package identity mismatch")
    require(composer["require"]["laravel/framework"].startswith("^13."), "Laravel 13 is required")
    require(composer["require"]["inertiajs/inertia-laravel"].startswith("^3."), "Inertia 3 is required")
    require(composer["require"]["php"].startswith("^8.3"), "Starter must remain PHP 8.3+ compatible")

    package = json.loads((PLATFORM / "package.json").read_text(encoding="utf-8"))
    require(package["name"] == "@kmjtechno/main-platform", "NPM package identity mismatch")
    require(package["dependencies"]["react"].startswith("^19."), "React 19 is required")
    require(package["dependencies"]["react-dom"].startswith("^19."), "React DOM 19 is required")
    require(package["dependencies"]["@inertiajs/react"].startswith("^3."), "Inertia React 3 is required")
    require("@laravel/passkeys" in package["dependencies"], "Passkey package must be present")
    require(package.get("private") is True, "Frontend package must remain private")

    env = (PLATFORM / ".env.example").read_text(encoding="utf-8")
    require('APP_NAME="KMJ TECHNO"' in env, "KMJ application identity missing")
    require("DB_CONNECTION=pgsql" in env, "PostgreSQL must be the application database target")
    require("DB_PORT=5432" in env, "PostgreSQL port must be 5432")
    require("DB_DATABASE=kmj_main" in env, "KMJ database name missing")

    require((PLATFORM / ".php-version").read_text(encoding="utf-8").strip() == "8.5", "PHP 8.5 pin missing")

    upstream = (PLATFORM / "UPSTREAM.md").read_text(encoding="utf-8")
    require(EXPECTED_UPSTREAM in upstream, "Runtime provenance does not match pinned upstream")

    boundary = (PLATFORM / "KMJ_BOUNDARY.md").read_text(encoding="utf-8")
    require("KMJ Cloud Nexus remains a separate engineering IDE" in boundary, "Cloud Nexus boundary missing")
    require("Production deployment" in boundary and "explicit owner approval" in boundary, "Production approval gate missing")

    phpunit = (PLATFORM / "phpunit.xml").read_text(encoding="utf-8")
    require('DB_CONNECTION" value="sqlite"' in phpunit, "CI tests must remain deterministic with SQLite")
    require('DB_DATABASE" value=":memory:"' in phpunit, "CI tests must use in-memory SQLite")

    print("KMJ platform runtime provenance verification PASS")


if __name__ == "__main__":
    main()
