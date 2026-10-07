from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "inventory" / "public-surface.yaml"
BACKLOG = ROOT / "work" / "backlog.yaml"
WEB_ROUTES = ROOT / "apps" / "platform" / "routes" / "web.php"
SETTINGS_ROUTES = ROOT / "apps" / "platform" / "routes" / "settings.php"
FORTIFY = ROOT / "apps" / "platform" / "config" / "fortify.php"
PUBLIC = ROOT / "apps" / "platform" / "public"
PUBLIC_SEO = ROOT / "apps" / "platform" / "resources" / "js" / "components" / "public-seo.tsx"
README = ROOT / "README.md"
BOUNDARY = ROOT / "apps" / "platform" / "KMJ_BOUNDARY.md"


def require(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise AssertionError(f"{label}: missing marker {marker!r}")


def public_assets(inventory: dict) -> list[str]:
    groups = inventory.get("public_assets")
    if not isinstance(groups, dict):
        raise AssertionError("public_assets must be grouped by asset class")
    assets: list[str] = []
    for name, values in groups.items():
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise AssertionError(f"public_assets.{name} must be a string list")
        assets.extend(values)
    if len(assets) != len(set(assets)):
        raise AssertionError("public asset inventory contains duplicate paths")
    return assets


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    inventory = yaml.safe_load(INVENTORY.read_text(encoding="utf-8-sig"))
    assert inventory.get("version") == 2
    assert inventory.get("scope") == "kmj_main_platform"
    assert inventory.get("cloud_nexus") == "untouched"

    web = WEB_ROUTES.read_text(encoding="utf-8")
    settings = SETTINGS_ROUTES.read_text(encoding="utf-8")
    fortify = FORTIFY.read_text(encoding="utf-8")
    public_seo = PUBLIC_SEO.read_text(encoding="utf-8")
    backlog = BACKLOG.read_text(encoding="utf-8")
    root_readme = README.read_text(encoding="utf-8")
    boundary = BOUNDARY.read_text(encoding="utf-8")

    require(web, "Route::get('/', function (PublicProductCatalog $products)", "native home route")
    require(web, "'products' => $products->all(),", "native home product portfolio")
    require(web, "Route::get('docs'", "public documentation route")
    require(web, "Route::get('insights'", "public insights route")
    require(web, "Route::get('support'", "public support route")
    require(web, "Route::get('dashboard'", "dashboard route")
    require(web, "Route::get('sandbox-licenses'", "sandbox license route")
    require(settings, "Route::get('.well-known/passkey-endpoints'", "passkey discovery")
    require(fortify, "Features::registration()", "registration")
    require(fortify, "Features::resetPasswords()", "password reset")
    require(backlog, "id: P0-02", "backlog")
    require(
        backlog,
        "title: Inventory current public URLs, assets and approved facts\n        status: done",
        "P0-02 status",
    )

    for asset in public_assets(inventory):
        path = PUBLIC / asset
        if not path.is_file():
            raise AssertionError(f"public asset missing: {path.relative_to(ROOT)}")

    localization = inventory.get("localization") or {}
    if localization.get("current_switch_transport") != "path_prefix":
        raise AssertionError("public locale switch must use explicit path prefixes")
    if localization.get("path_prefixes") != ["/en", "/hi"]:
        raise AssertionError("public locale prefixes must be /en and /hi")
    if localization.get("seo_path_locales_present") is not True:
        raise AssertionError("SEO locale paths are not marked present")
    if localization.get("resource_hreflang_alternates") is not True:
        raise AssertionError("resource hreflang evidence is not enabled")
    require(web, "Route::prefix('{locale}')", "localized public route group")
    require(public_seo, "localePath('en')", "English locale URL")
    require(public_seo, "localePath('hi')", "Hindi locale URL")
    require(public_seo, 'hrefLang="en"', "English hreflang")
    require(public_seo, 'hrefLang="hi"', "Hindi hreflang")
    require(public_seo, 'hrefLang="x-default"', "default hreflang")

    visual_paths = [
        PUBLIC / "assets/products/kmj-cinema-platform.webp",
        PUBLIC / "assets/products/kmj-360-dome.svg",
        PUBLIC / "assets/products/kmj-cinema-player.svg",
    ]
    visual_hashes = [sha256(path) for path in visual_paths]
    if len(set(visual_hashes)) != len(visual_hashes):
        raise AssertionError("cinema product visuals must be distinct")

    gap_codes = {
        item.get("code")
        for item in inventory.get("observed_gaps", [])
        if isinstance(item, dict)
    }
    if {"PRODUCT_VISUAL_360_DOME_MISSING", "PRODUCT_VISUAL_CINEMA_PLAYER_MISSING"} & gap_codes:
        raise AssertionError("resolved product visual gaps remain in inventory")

    require(root_readme, "Git is the source of truth.", "root README")
    require(root_readme, "Paid AI fallback is prohibited. Unknown cost is not free.", "root README")
    require(boundary, "KMJ Cloud Nexus remains a separate engineering IDE", "application boundary")
    require(
        boundary,
        "Production deployment, DNS, billing and destructive data actions require explicit owner approval.",
        "application boundary",
    )

    print("KMJ public surface inventory verification PASS")


if __name__ == "__main__":
    main()
