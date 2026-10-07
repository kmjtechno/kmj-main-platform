from __future__ import annotations

import asyncio
from contextlib import closing
from dataclasses import dataclass
import json
import hashlib
import math
import sqlite3
import time
from email.utils import parsedate_to_datetime
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
    allow_confidential: bool = False


@dataclass(frozen=True)
class RouteCandidate:
    model_id: str
    owner: str
    score: int
    reason: str
    provider: str = "9router"
    base_url: str = ""
    api_key: str = ""
    allow_confidential: bool = False


class FreeCloudRouter:
    """Federated strict-zero router.

    Multiple cloud transports may be configured, but KMJ policy remains
    authoritative: paid fallback is prohibited and unknown cost is never free.
    Direct providers are accepted only for explicit ``:free``/allowlisted
    models or when the provider account is explicitly verified as free-tier.
    """

    BUILTIN_PROVIDERS = {
        "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", False),
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
            or "http://127.0.0.1:18765/v1"
        ).rstrip("/")
        self.api_key = os.getenv("KMJ_9ROUTER_API_KEY", "")
        self.timeout = float(os.getenv("KMJ_9ROUTER_TIMEOUT_SECONDS", "12"))
        self.max_failover_models = max(1, min(32, int(
            os.getenv("KMJ_MAX_FREE_FAILOVER_MODELS", "6")
        )))
        self.state_path = Path(os.getenv("KMJ_ROUTER_STATE_DB", str(Path.home() / ".kmj/model-router-state.sqlite3")))
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

    @staticmethod
    def _normalize_classification(data_classification: str) -> str:
        value = (data_classification or "confidential").strip().lower()
        return value if value in {"public", "confidential"} else "confidential"

    def _provider_headers(
        self,
        provider: ProviderEndpoint,
        data_classification: str = "confidential",
    ) -> dict[str, str]:
        headers = self._headers(provider.api_key)
        if provider.name == "9router":
            headers["X-KMJ-Sensitivity"] = self._normalize_classification(
                data_classification
            )
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
                allow_confidential=False,
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

        cloudflare_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        cloudflare_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        if cloudflare_token and cloudflare_account:
            providers.append(
                ProviderEndpoint(
                    name="cloudflare",
                    base_url=(
                        "https://api.cloudflare.com/client/v4/accounts/"
                        f"{cloudflare_account}/ai/v1"
                    ),
                    api_key=cloudflare_token,
                    priority=self._provider_priority("cloudflare"),
                    allow_confidential=False,
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
                    allow_confidential = item.get("allow_confidential") is True
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
        data_classification: str = "confidential",
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{provider.base_url}/models",
                headers=self._provider_headers(provider, data_classification),
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
            enriched["_kmj_allow_confidential"] = (
                provider.allow_confidential is True
                and item.get("kmj_allow_confidential", False) is True
            )
            models.append(enriched)
        return models

    async def discover(
        self,
        data_classification: str = "confidential",
    ) -> list[dict[str, Any]]:
        classification = self._normalize_classification(data_classification)
        providers = self.providers()
        results = await asyncio.gather(
            *(
                self._discover_provider(provider, classification)
                for provider in providers
            ),
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
            allow_confidential = item.get("_kmj_allow_confidential", False) is True
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

        health = self._model_health() if candidates else {}
        now = time.time()
        return sorted(
            candidates,
            key=lambda candidate: (
                -self._recent_success(candidate, health, now),
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
        ranked = self.rank(
            await self.discover(data_classification),
            route,
            data_classification,
        )
        if not ranked:
            raise NoFreeRouteAvailable("NO_FREE_ROUTE_AVAILABLE")
        return ranked[0]

    def _cooldown(self, candidate: RouteCandidate, seconds: float | None = None) -> bool:
        # Endpoint-level cooldown protects shared provider/account quotas across
        # worker processes. No prompts or credentials are persisted.
        key = hashlib.sha256(f"{candidate.provider}:{candidate.base_url}".encode()).hexdigest()
        try:
            self.state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.state_path, timeout=2)) as db, db:
                os.chmod(self.state_path, 0o600)
                db.execute("CREATE TABLE IF NOT EXISTS cooldown (endpoint TEXT PRIMARY KEY, until REAL NOT NULL)")
                if seconds is not None:
                    db.execute("INSERT INTO cooldown VALUES (?, ?) ON CONFLICT(endpoint) DO UPDATE SET until = MAX(until, excluded.until)",
                               (key, time.time() + seconds))
                row = db.execute("SELECT until FROM cooldown WHERE endpoint = ?", (key,)).fetchone()
                return bool(row and row[0] > time.time())
        except (OSError, sqlite3.Error) as exc:
            raise NoFreeRouteAvailable("ROUTER_STATE_UNAVAILABLE") from exc

    @staticmethod
    def _model_key(candidate: RouteCandidate) -> str:
        # Hash the full identity so URL credentials/query data cannot enter state.
        identity = [candidate.provider, candidate.base_url.rstrip("/"), candidate.model_id]
        return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()

    def _model_health(self, candidate=None, *, cooldown_seconds=None, succeeded=False):
        """Persist only hashed route identity and availability timestamps."""
        try:
            self.state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.state_path, timeout=2)) as db, db:
                os.chmod(self.state_path, 0o600)
                db.execute("""CREATE TABLE IF NOT EXISTS model_health (
                    route TEXT PRIMARY KEY, cooldown_until REAL NOT NULL,
                    last_success REAL NOT NULL)""")
                if candidate is not None:
                    key = self._model_key(candidate)
                    now = time.time()
                    if succeeded:
                        db.execute("""INSERT INTO model_health VALUES (?,0,?)
                            ON CONFLICT(route) DO UPDATE SET cooldown_until=0,
                            last_success=excluded.last_success""", (key, now))
                    elif cooldown_seconds is not None:
                        db.execute("""INSERT INTO model_health VALUES (?,?,0)
                            ON CONFLICT(route) DO UPDATE SET
                            cooldown_until=MAX(cooldown_until,excluded.cooldown_until)""",
                            (key, now + cooldown_seconds))
                return {row[0]: (row[1], row[2]) for row in
                        db.execute("SELECT route,cooldown_until,last_success FROM model_health")}
        except (OSError, sqlite3.Error) as exc:
            raise NoFreeRouteAvailable("ROUTER_STATE_UNAVAILABLE") from exc

    def _recent_success(self, candidate, health, now):
        until, success = health.get(self._model_key(candidate), (0, 0))
        return success if until <= now and 0 < success <= now < success + 3600 else 0

    def _record_cooldown(self, candidate: RouteCandidate, exc: Exception) -> None:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
            self._model_health(candidate, cooldown_seconds=900)
        elif isinstance(exc, httpx.ReadTimeout) or (
                isinstance(exc, RuntimeError) and str(exc) == "INCOMPLETE_COMPLETION"):
            self._model_health(candidate, cooldown_seconds=60)
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403, 429, 503}:
            delay = 300.0 if exc.response.status_code in {401, 403} else 60.0
            retry = exc.response.headers.get("Retry-After", "")
            if retry:
                try:
                    parsed = float(retry)
                except ValueError:
                    try:
                        parsed = parsedate_to_datetime(retry).timestamp() - time.time()
                    except (TypeError, ValueError, OverflowError):
                        parsed = delay
                if math.isfinite(parsed):
                    delay = max(delay, parsed)
            self._cooldown(candidate, delay)
        elif isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            self._cooldown(candidate, 30)

    async def complete(
        self,
        messages: list[dict[str, str]],
        route: str = "coding",
        temperature: float = 0.1,
        data_classification: str = "confidential",
    ) -> dict[str, Any]:
        from controller.local_fallback import validate_messages, LocalFallbackUnavailable
        try:
            validate_messages(messages)
        except LocalFallbackUnavailable as exc:
            raise NoFreeRouteAvailable(str(exc)) from exc
        ranked = self.rank(
            await self.discover(data_classification),
            route,
            data_classification,
        )
        if not ranked:
            return await self._final_fallback(messages, temperature, data_classification, [])

        attempts: list[dict[str, str]] = []
        # Interleave providers so a large catalog cannot monopolize the budget.
        groups: dict[str, list[RouteCandidate]] = {}
        for candidate in ranked:
            groups.setdefault(candidate.provider, []).append(candidate)
        ordered = []
        while any(groups.values()):
            for group in groups.values():
                if group:
                    ordered.append(group.pop(0))
        attempted = 0
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False, follow_redirects=False) as client:
            for index, candidate in enumerate(ordered):
                health = self._model_health()
                model_until = health.get(self._model_key(candidate), (0, 0))[0]
                if self._cooldown(candidate) or model_until > time.time():
                    attempts.append({"provider":candidate.provider, "model":candidate.model_id, "result":"cooldown"})
                    continue
                if attempted >= self.max_failover_models:
                    return await self._final_fallback(
                        messages, temperature, data_classification, attempts,
                        reason="cloud_attempt_budget_exhausted",
                        unattempted_cloud_candidates=len(ordered) - index,
                    )
                attempted += 1
                try:
                    response = await client.post(
                        f"{candidate.base_url}/chat/completions",
                        headers={
                            **self._headers(candidate.api_key),
                            **(
                                {
                                    "X-KMJ-Sensitivity":
                                        self._normalize_classification(
                                            data_classification
                                        )
                                }
                                if candidate.provider == "9router"
                                else {}
                            ),
                        },
                        json={
                            "model": candidate.model_id,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": 2048,
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
                    if (not choices or not isinstance(choices[0], dict)
                            or choices[0].get("finish_reason") != "stop"
                            or not isinstance(choices[0].get("message", {}).get("content"), str)
                            or not choices[0]["message"]["content"].strip()):
                        raise RuntimeError("INCOMPLETE_COMPLETION")
                    self._model_health(candidate, succeeded=True)
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
                except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                    self._record_cooldown(candidate, exc)
                    attempts.append(
                        {
                            "provider": candidate.provider,
                            "model": candidate.model_id,
                            "result": type(exc).__name__,
                        }
                    )

        return await self._final_fallback(messages, temperature, data_classification, attempts)

    async def _final_fallback(
        self, messages, temperature, data_classification, attempts, *,
        reason="NO_ELIGIBLE_CLOUD_ROUTE_AVAILABLE", unattempted_cloud_candidates=0,
    ):
        from controller.local_fallback import complete, enabled, LocalFallbackUnavailable
        try:
            result = await self._official_free_client(messages, data_classification=data_classification)
            if attempts:
                result = dict(result, attempts=attempts + result.get("attempts", []))
            return result
        except NoFreeRouteAvailable as cloud_error:
            if not enabled() or self.config.get("policy", {}).get("local_llm") != "emergency_cpu_only":
                raise
            combined = attempts + [{"provider":"opencode-client", "model":"", "result":str(cloud_error)}]
            try:
                result = await complete(messages, temperature=temperature)
                result["attempts"] = combined + result.get("attempts", [])
                result["fallback_reason"] = reason
                result["unattempted_cloud_candidates"] = unattempted_cloud_candidates
                return result
            except (LocalFallbackUnavailable, OSError) as exc:
                raise NoFreeRouteAvailable(str(exc)) from exc

    async def _official_free_client(
        self,
        messages: list[dict[str, str]],
        *,
        data_classification: str = "confidential",
    ) -> dict[str, Any]:
        from controller.opencode_free import OpenCodeUnavailable, complete

        if self._normalize_classification(data_classification) != "public":
            raise NoFreeRouteAvailable("NO_CONFIDENTIAL_FREE_ROUTE_AVAILABLE")

        try:
            return await asyncio.to_thread(complete, messages)
        except OpenCodeUnavailable as exc:
            raise NoFreeRouteAvailable(str(exc)) from exc

    async def status(self) -> dict[str, Any]:
        models = await self.discover("public")
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
                        "allow_confidential": item.get("_kmj_allow_confidential", False) is True,
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
            "local_llm": self.config.get("policy", {}).get("local_llm", "prohibited"),
            "max_free_failover_models": self.max_failover_models,
            "models": eligible,
        }
