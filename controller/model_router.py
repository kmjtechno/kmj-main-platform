from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROUTER_CONFIG = ROOT / "config" / "free-cloud-routing.yaml"


class NoFreeRouteAvailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderEndpoint:
    name: str
    base_url: str
    api_key: str = ""
    priority: int = 0
    allow_confidential: bool = True


@dataclass(frozen=True)
class RouteCandidate:
    model_id: str
    owner: str
    score: int
    reason: str
    provider: str = "9router"
    base_url: str = ""
    api_key: str = ""
    allow_confidential: bool = True


class FreeCloudRouter:
    """Federated strict-zero router.

    Multiple cloud transports may be configured, but KMJ policy remains
    authoritative: paid fallback is prohibited and unknown cost is never free.
    Direct providers are accepted only for explicit ``:free``/allowlisted
    models or when the provider account is explicitly verified as free-tier.
    """

    BUILTIN_PROVIDERS = {
        "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", True),
        "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", False),
        "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", False),
        "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", False),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "GEMINI_API_KEY",
            False,
        ),
        "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", False),
        "zai": ("https://api.z.ai/api/paas/v4", "ZAI_API_KEY", False),
        "ollama-cloud": ("https://ollama.com/v1", "OLLAMA_API_KEY", False),
    }

    ANONYMOUS_PUBLIC_PROVIDERS = {
        "kilo": "https://api.kilo.ai/api/gateway",
    }

    def __init__(self) -> None:
        self.config = yaml.safe_load(ROUTER_CONFIG.read_text(encoding="utf-8"))
        self.base_url = (
            os.getenv("KMJ_9ROUTER_BASE_URL", "").strip()
            or "http://127.0.0.1:20128/v1"
        ).rstrip("/")
        self.api_key = os.getenv("KMJ_9ROUTER_API_KEY", "")
        self.timeout = float(os.getenv("KMJ_9ROUTER_TIMEOUT_SECONDS", "12"))
        self.max_failover_models = int(
            os.getenv("KMJ_MAX_FREE_FAILOVER_MODELS", "6")
        )
        self._last_provider_errors: dict[str, str] = {}

    @staticmethod
    def _headers(api_key: str = "") -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _explicit_zero_models(self) -> set[str]:
        values = set(
            self.config.get("verified_zero", {}).get("explicit_models", [])
        )
        env_values = os.getenv("KMJ_VERIFIED_ZERO_MODELS", "")
        values.update(x.strip() for x in env_values.split(",") if x.strip())
        return values

    def _verified_free_providers(self) -> set[str]:
        configured = set(
            self.config.get("verified_zero", {}).get(
                "verified_free_provider_accounts", []
            )
        )
        env_values = os.getenv("KMJ_VERIFIED_FREE_PROVIDERS", "")
        configured.update(
            x.strip().lower() for x in env_values.split(",") if x.strip()
        )
        return {x.lower() for x in configured}

    def _provider_priority(self, name: str) -> int:
        order = self.config.get("providers", {}).get("priority", [])
        try:
            return max(0, 30 - order.index(name) * 4)
        except ValueError:
            return 0

    def providers(self) -> list[ProviderEndpoint]:
        providers = [
            ProviderEndpoint(
                name="9router",
                base_url=self.base_url,
                api_key=self.api_key,
                priority=self._provider_priority("9router"),
                allow_confidential=True,
            )
        ]

        for name, (base_url, key_env, allow_confidential) in self.BUILTIN_PROVIDERS.items():
            key = os.getenv(key_env, "").strip()
            if key:
                providers.append(
                    ProviderEndpoint(
                        name=name,
                        base_url=base_url.rstrip("/"),
                        api_key=key,
                        priority=self._provider_priority(name),
                        allow_confidential=allow_confidential,
                    )
                )

        if os.getenv("KMJ_ENABLE_PUBLIC_FREE_PROVIDERS", "").strip().lower() in {"1", "true", "yes", "on"}:
            for name, base_url in self.ANONYMOUS_PUBLIC_PROVIDERS.items():
                providers.append(
                    ProviderEndpoint(
                        name=name,
                        base_url=base_url.rstrip("/"),
                        priority=self._provider_priority(name),
                        allow_confidential=False,
                    )
                )

        raw_custom = os.getenv("KMJ_FREE_PROVIDER_ENDPOINTS_JSON", "").strip()
        if raw_custom:
            try:
                custom = json.loads(raw_custom)
            except json.JSONDecodeError:
                custom = []
            if isinstance(custom, list):
                for item in custom:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip().lower()
                    base_url = str(item.get("base_url", "")).strip().rstrip("/")
                    key_env = str(item.get("api_key_env", "")).strip()
                    api_key = os.getenv(key_env, "").strip() if key_env else ""
                    allow_confidential = bool(item.get("allow_confidential", False))
                    if name and base_url:
                        providers.append(
                            ProviderEndpoint(
                                name=name,
                                base_url=base_url,
                                api_key=api_key,
                                priority=self._provider_priority(name),
                                allow_confidential=allow_confidential,
                            )
                        )

        deduped: dict[tuple[str, str], ProviderEndpoint] = {}
        for provider in providers:
            deduped[(provider.name, provider.base_url)] = provider
        return list(deduped.values())

    def _eligible(
        self,
        model_id: str,
        owner: str,
        provider: str = "9router",
    ) -> tuple[bool, str]:
        model_id_l = model_id.lower()
        owner_l = owner.lower()
        provider_l = provider.lower()

        denied = self.config.get("deny", {}).get("model_fragments", [])
        if any(fragment.lower() in model_id_l for fragment in denied):
            return False, "denied-fragment"

        if model_id_l.endswith(":free"):
            return True, "explicit-free-suffix"

        if model_id in self._explicit_zero_models():
            return True, "explicit-zero-allowlist"

        if provider_l in self._verified_free_providers():
            return True, "verified-free-provider-account"

        # Provider/owner trust is allowed only behind the locally controlled
        # aggregator. Applying it to a direct cloud account could silently
        # convert a free route into a billable one if the account tier changes.
        if provider_l == "9router":
            prefixes = self.config.get("verified_zero", {}).get(
                "trusted_prefixes", []
            )
            if any(
                model_id_l.startswith(prefix.lower()) for prefix in prefixes
            ):
                return True, "trusted-free-provider-prefix"

            owners = self.config.get("verified_zero", {}).get(
                "trusted_owners", []
            )
            if owner_l and owner_l in {x.lower() for x in owners}:
                return True, "trusted-free-provider-owner"

        return False, "cost-not-verified-zero"

    async def _discover_provider(
        self,
        provider: ProviderEndpoint,
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{provider.base_url}/models",
                headers=self._headers(provider.api_key),
            )
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data", []) if isinstance(payload, dict) else []
        models: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            enriched = dict(item)
            enriched["_kmj_provider"] = provider.name
            enriched["_kmj_base_url"] = provider.base_url
            enriched["_kmj_api_key"] = provider.api_key
            enriched["_kmj_provider_priority"] = provider.priority
            enriched["_kmj_allow_confidential"] = provider.allow_confidential
            models.append(enriched)
        return models

    async def discover(self) -> list[dict[str, Any]]:
        providers = self.providers()
        results = await asyncio.gather(
            *(self._discover_provider(provider) for provider in providers),
            return_exceptions=True,
        )
        models: list[dict[str, Any]] = []
        self._last_provider_errors = {}
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                self._last_provider_errors[provider.name] = type(result).__name__
                continue
            models.extend(result)
        return models

    def rank(
        self,
        models: list[dict[str, Any]],
        route: str,
        data_classification: str = "confidential",
    ) -> list[RouteCandidate]:
        profile = self.config.get("routes", {}).get(
            route,
            self.config.get("routes", {}).get("coding", {}),
        )
        preferences = [x.lower() for x in profile.get("prefer", [])]
        candidates: list[RouteCandidate] = []
        classification = (data_classification or "confidential").strip().lower()
        if classification not in {"public", "confidential"}:
            classification = "confidential"

        for item in models:
            model_id = str(item.get("id", ""))
            owner = str(item.get("owned_by", ""))
            provider = str(item.get("_kmj_provider", "9router"))
            eligible, reason = self._eligible(model_id, owner, provider)
            if not eligible:
                continue
            allow_confidential = bool(item.get("_kmj_allow_confidential", True))
            if classification == "confidential" and not allow_confidential:
                continue

            text = f"{model_id} {owner} {provider}".lower()
            score = 100 + int(item.get("_kmj_provider_priority", 0))
            for index, token in enumerate(preferences):
                if token in text:
                    score += max(1, 50 - index * 5)
            candidates.append(
                RouteCandidate(
                    model_id=model_id,
                    owner=owner,
                    score=score,
                    reason=reason,
                    provider=provider,
                    base_url=str(item.get("_kmj_base_url", self.base_url)),
                    api_key=str(item.get("_kmj_api_key", self.api_key)),
                    allow_confidential=allow_confidential,
                )
            )

        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.provider,
                candidate.model_id,
            ),
        )

    async def select(
        self,
        route: str = "coding",
        data_classification: str = "confidential",
    ) -> RouteCandidate:
        ranked = self.rank(await self.discover(), route, data_classification)
        if not ranked:
            raise NoFreeRouteAvailable("NO_FREE_ROUTE_AVAILABLE")
        return ranked[0]

    async def complete(
        self,
        messages: list[dict[str, str]],
        route: str = "coding",
        temperature: float = 0.1,
        data_classification: str = "confidential",
    ) -> dict[str, Any]:
        ranked = self.rank(await self.discover(), route, data_classification)
        if not ranked:
            return await self._official_free_client(messages)

        attempts: list[dict[str, str]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for candidate in ranked[: self.max_failover_models]:
                try:
                    response = await client.post(
                        f"{candidate.base_url}/chat/completions",
                        headers=self._headers(candidate.api_key),
                        json={
                            "model": candidate.model_id,
                            "messages": messages,
                            "temperature": temperature,
                            "stream": False,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    choices = (
                        payload.get("choices", [])
                        if isinstance(payload, dict)
                        else []
                    )
                    if not choices:
                        raise RuntimeError("EMPTY_COMPLETION")
                    return {
                        "model": candidate.model_id,
                        "provider": candidate.provider,
                        "owner": candidate.owner,
                        "verification": candidate.reason,
                        "attempts": attempts
                        + [
                            {
                                "provider": candidate.provider,
                                "model": candidate.model_id,
                                "result": "success",
                            }
                        ],
                        "response": payload,
                    }
                except Exception as exc:
                    attempts.append(
                        {
                            "provider": candidate.provider,
                            "model": candidate.model_id,
                            "result": type(exc).__name__,
                        }
                    )

        return await self._official_free_client(messages)

    async def _official_free_client(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        from controller.opencode_free import OpenCodeUnavailable, complete

        try:
            return await asyncio.to_thread(complete, messages)
        except OpenCodeUnavailable as exc:
            raise NoFreeRouteAvailable(str(exc)) from exc

    async def status(self) -> dict[str, Any]:
        models = await self.discover()
        eligible: list[dict[str, Any]] = []
        rejected = 0
        for item in models:
            provider = str(item.get("_kmj_provider", "9router"))
            ok, reason = self._eligible(
                str(item.get("id", "")),
                str(item.get("owned_by", "")),
                provider,
            )
            if ok:
                eligible.append(
                    {
                        "id": item.get("id"),
                        "owned_by": item.get("owned_by"),
                        "provider": provider,
                        "verification": reason,
                        "allow_confidential": bool(
                            item.get("_kmj_allow_confidential", True)
                        ),
                    }
                )
            else:
                rejected += 1

        confidential_eligible = [
            item for item in eligible if item["allow_confidential"]
        ]
        configured = [provider.name for provider in self.providers()]
        reachable = sorted(
            {
                str(item.get("_kmj_provider", "9router"))
                for item in models
            }
        )
        return {
            "router": "KMJ federated verified-zero router",
            "configured_providers": configured,
            "reachable_providers": reachable,
            "provider_errors": self._last_provider_errors,
            "reachable": bool(reachable),
            "discovered": len(models),
            "eligible_verified_zero": len(eligible),
            "eligible_public_verified_zero": len(eligible),
            "eligible_confidential_verified_zero": len(confidential_eligible),
            "rejected_unknown_or_paid": rejected,
            "paid_fallback": "PROHIBITED",
            "unknown_cost_is_free": False,
            "local_llm": "PROHIBITED",
            "max_free_failover_models": self.max_failover_models,
            "models": eligible,
        }
