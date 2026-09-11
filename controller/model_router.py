from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROUTER_CONFIG = ROOT / "config" / "free-cloud-routing.yaml"


class NoFreeRouteAvailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RouteCandidate:
    model_id: str
    owner: str
    score: int
    reason: str


class FreeCloudRouter:
    """Strict verified-zero model selector in front of 9Router.

    9Router is transport/discovery only. KMJ policy is authoritative: paid
    routes are prohibited and unknown cost is never treated as free.
    """

    def __init__(self) -> None:
        self.config = yaml.safe_load(ROUTER_CONFIG.read_text(encoding="utf-8"))
        self.base_url = (os.getenv("KMJ_9ROUTER_BASE_URL", "").strip() or "http://127.0.0.1:20128/v1").rstrip("/")
        self.api_key = os.getenv("KMJ_9ROUTER_API_KEY", "")
        self.timeout = float(os.getenv("KMJ_9ROUTER_TIMEOUT_SECONDS", "12"))
        self.max_failover_models = int(os.getenv("KMJ_MAX_FREE_FAILOVER_MODELS", "4"))

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _explicit_zero_models(self) -> set[str]:
        values = set(self.config.get("verified_zero", {}).get("explicit_models", []))
        env_values = os.getenv("KMJ_VERIFIED_ZERO_MODELS", "")
        values.update(x.strip() for x in env_values.split(",") if x.strip())
        return values

    def _eligible(self, model_id: str, owner: str) -> tuple[bool, str]:
        model_id_l = model_id.lower()
        owner_l = owner.lower()

        denied = self.config.get("deny", {}).get("model_fragments", [])
        if any(fragment.lower() in model_id_l for fragment in denied):
            return False, "denied-fragment"

        if model_id_l.endswith(":free"):
            return True, "explicit-free-suffix"

        if model_id in self._explicit_zero_models():
            return True, "explicit-zero-allowlist"

        prefixes = self.config.get("verified_zero", {}).get("trusted_prefixes", [])
        if any(model_id_l.startswith(prefix.lower()) for prefix in prefixes):
            return True, "trusted-free-provider-prefix"

        owners = self.config.get("verified_zero", {}).get("trusted_owners", [])
        if owner_l and owner_l in {x.lower() for x in owners}:
            return True, "trusted-free-provider-owner"

        return False, "cost-not-verified-zero"

    async def discover(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers())
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return [item for item in data if isinstance(item, dict) and item.get("id")]

    def rank(self, models: list[dict[str, Any]], route: str) -> list[RouteCandidate]:
        profile = self.config.get("routes", {}).get(route, self.config.get("routes", {}).get("coding", {}))
        preferences = [x.lower() for x in profile.get("prefer", [])]
        candidates: list[RouteCandidate] = []

        for item in models:
            model_id = str(item.get("id", ""))
            owner = str(item.get("owned_by", ""))
            eligible, reason = self._eligible(model_id, owner)
            if not eligible:
                continue

            text = f"{model_id} {owner}".lower()
            score = 100
            for index, token in enumerate(preferences):
                if token in text:
                    score += max(1, 50 - index * 5)
            candidates.append(RouteCandidate(model_id, owner, score, reason))

        return sorted(candidates, key=lambda c: (-c.score, c.model_id))

    async def select(self, route: str = "coding") -> RouteCandidate:
        models = await self.discover()
        ranked = self.rank(models, route)
        if not ranked:
            raise NoFreeRouteAvailable("NO_FREE_ROUTE_AVAILABLE")
        return ranked[0]

    async def complete(
        self,
        messages: list[dict[str, str]],
        route: str = "coding",
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        models = await self.discover()
        ranked = self.rank(models, route)
        if not ranked:
            raise NoFreeRouteAvailable("NO_FREE_ROUTE_AVAILABLE")

        attempts: list[dict[str, str]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for candidate in ranked[: self.max_failover_models]:
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json={
                            "model": candidate.model_id,
                            "messages": messages,
                            "temperature": temperature,
                            "stream": False,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    choices = payload.get("choices", []) if isinstance(payload, dict) else []
                    if not choices:
                        raise RuntimeError("EMPTY_COMPLETION")
                    return {
                        "model": candidate.model_id,
                        "owner": candidate.owner,
                        "verification": candidate.reason,
                        "attempts": attempts + [{"model": candidate.model_id, "result": "success"}],
                        "response": payload,
                    }
                except Exception as exc:
                    attempts.append({"model": candidate.model_id, "result": type(exc).__name__})

        raise NoFreeRouteAvailable("ALL_VERIFIED_FREE_ROUTES_FAILED")

    async def status(self) -> dict[str, Any]:
        try:
            models = await self.discover()
            eligible = []
            rejected = 0
            for item in models:
                ok, reason = self._eligible(str(item.get("id", "")), str(item.get("owned_by", "")))
                if ok:
                    eligible.append({"id": item.get("id"), "owned_by": item.get("owned_by"), "verification": reason})
                else:
                    rejected += 1
            return {
                "router": "9Router",
                "base_url": self.base_url,
                "reachable": True,
                "discovered": len(models),
                "eligible_verified_zero": len(eligible),
                "rejected_unknown_or_paid": rejected,
                "paid_fallback": "PROHIBITED",
                "unknown_cost_is_free": False,
                "local_llm": "PROHIBITED",
                "max_free_failover_models": self.max_failover_models,
                "models": eligible,
            }
        except Exception as exc:
            return {
                "router": "9Router",
                "base_url": self.base_url,
                "reachable": False,
                "error": type(exc).__name__,
                "safe_result": "NO_FREE_ROUTE_AVAILABLE",
                "paid_fallback": "PROHIBITED",
                "unknown_cost_is_free": False,
            }
