from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "modules.yaml"
SOURCE_EXTENSIONS = {".php", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs"}
PROVIDER_TERMS = re.compile(r"\b(openai|anthropic|openrouter|stripe|razorpay|paypal)\b", re.I)
CLOUD_NEXUS_TERMS = re.compile(r"(kmj-autonomous-cloud-ide|cloud_nexus|cloud\s+nexus)", re.I)
PERSISTENCE_TERMS = ("/Persistence/", "\\Persistence\\", "/Models/", "\\Models\\")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_acyclic(graph: dict[str, set[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise AssertionError(f"Module dependency cycle detected at {node}")
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for module in graph:
        visit(module)


def verify_manifest(manifest: dict) -> dict[str, dict]:
    assert manifest.get("version") == 1
    assert manifest.get("architecture") == "modular_monolith"
    assert manifest.get("cross_module_write_policy") == "interfaces_or_events_only"
    assert manifest.get("persistence_policy") == "module_owned"
    assert manifest.get("cloud_nexus_dependency") == "prohibited"

    modules = manifest.get("modules") or {}
    required = {"identity", "organizations", "catalog", "entitlements", "licensing", "releases"}
    missing = required - set(modules)
    assert not missing, f"Missing required first-slice modules: {sorted(missing)}"

    graph: dict[str, set[str]] = {}
    for name, config in modules.items():
        dependencies = set(config.get("allowed_dependencies") or [])
        unknown = dependencies - set(modules)
        assert not unknown, f"{name}: unknown dependencies {sorted(unknown)}"
        assert name not in dependencies, f"{name}: self dependency is prohibited"
        graph[name] = dependencies

        path = ROOT / config["path"]
        module_file = path / "MODULE.yaml"
        assert module_file.is_file(), f"{name}: missing {module_file.relative_to(ROOT)}"
        local = load_yaml(module_file)
        assert local.get("name") == name, f"{name}: MODULE.yaml name mismatch"
        assert set(local.get("allowed_dependencies") or []) == dependencies, (
            f"{name}: MODULE.yaml dependency mismatch"
        )
        assert local.get("persistence_namespace") == name, (
            f"{name}: persistence namespace must be module-owned"
        )

    assert_acyclic(graph)
    return modules


def iter_source_files(module_path: Path):
    if not module_path.exists():
        return
    for path in module_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
            yield path


def verify_source_boundaries(modules: dict[str, dict]) -> None:
    for module_name, config in modules.items():
        allowed = set(config.get("allowed_dependencies") or [])
        module_path = ROOT / config["path"]
        for source in iter_source_files(module_path):
            text = source.read_text(encoding="utf-8", errors="replace")
            rel = source.relative_to(ROOT)

            if CLOUD_NEXUS_TERMS.search(text):
                raise AssertionError(f"{rel}: Cloud Nexus implementation dependency is prohibited")

            if PROVIDER_TERMS.search(text):
                raise AssertionError(
                    f"{rel}: provider-specific SDK/reference found inside domain module; use an adapter"
                )

            normalized = text.replace("\\", "/").lower()
            for other_name, other_config in modules.items():
                if other_name == module_name:
                    continue
                token = f"domain-{other_name}".lower()
                if token not in normalized:
                    continue
                if other_name not in allowed:
                    raise AssertionError(
                        f"{rel}: undeclared domain dependency on {other_name}"
                    )
                if any(term.lower().replace("\\", "/") in normalized for term in PERSISTENCE_TERMS):
                    raise AssertionError(
                        f"{rel}: cross-module persistence/model import is prohibited"
                    )


def main() -> None:
    manifest = load_yaml(MANIFEST)
    modules = verify_manifest(manifest)
    verify_source_boundaries(modules)
    print("KMJ architecture boundary verification PASS")


if __name__ == "__main__":
    main()
