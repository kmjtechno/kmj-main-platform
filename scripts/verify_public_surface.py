from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "inventory" / "public-surface.yaml"
BACKLOG = ROOT / "work" / "backlog.yaml"
WEB_ROUTES = ROOT / "apps" / "platform" / "routes" / "web.php"
SETTINGS_ROUTES = ROOT / "apps" / "platform" / "routes" / "settings.php"
FORTIFY = ROOT / "apps" / "platform" / "config" / "fortify.php"
PUBLIC = ROOT / "apps" / "platform" / "public"
README = ROOT / "README.md"
BOUNDARY = ROOT / "apps" / "platform" / "KMJ_BOUNDARY.md"


def require(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise AssertionError(f"{label}: missing marker {marker!r}")


def main() -> None:
    inventory = yaml.safe_load(INVENTORY.read_text(encoding="utf-8-sig"))
    assert inventory.get("version") == 1
    assert inventory.get("scope") == "kmj_main_platform"
    assert inventory.get("cloud_nexus") == "untouched"

    web = WEB_ROUTES.read_text(encoding="utf-8")
    settings = SETTINGS_ROUTES.read_text(encoding="utf-8")
    fortify = FORTIFY.read_text(encoding="utf-8")
    backlog = BACKLOG.read_text(encoding="utf-8")
    root_readme = README.read_text(encoding="utf-8")
    boundary = BOUNDARY.read_text(encoding="utf-8")

    require(web, "Route::inertia('/', 'welcome')", "home route")
    require(web, "Route::get('dashboard'", "dashboard route")
    require(web, "Route::get('sandbox-licenses'", "sandbox license route")
    require(settings, "Route::get('.well-known/passkey-endpoints'", "passkey discovery")
    require(fortify, "Features::registration()", "registration")
    require(fortify, "Features::resetPasswords()", "password reset")
    require(backlog, "id: P0-02", "backlog")
    require(backlog, "title: Inventory current public URLs, assets and approved facts\n        status: done", "P0-02 status")

    for asset in inventory.get("public_assets", []):
        path = PUBLIC / asset
        if not path.is_file():
            raise AssertionError(f"public asset missing: {path.relative_to(ROOT)}")

    require(root_readme, "Git is the source of truth.", "root README")
    require(root_readme, "Paid AI fallback is prohibited. Unknown cost is not free.", "root README")
    require(boundary, "KMJ Cloud Nexus remains a separate engineering IDE", "application boundary")
    require(boundary, "Production deployment, DNS, billing and destructive data actions require explicit owner approval.", "application boundary")

    print("KMJ public surface inventory verification PASS")


if __name__ == "__main__":
    main()
