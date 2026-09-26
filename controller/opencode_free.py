"""Use the official OpenCode client with freshly verified zero-cost models."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib
from typing import Callable
import urllib.request

DEFAULT_MODELS = [
    "opencode/mimo-v2.6-flash-free",
    "opencode/ling-3.0-flash-fin-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/big-pickle",
]
PRICE_ROOT = "https://raw.githubusercontent.com/anomalyco/models.dev/dev/providers/opencode/models"


class OpenCodeUnavailable(RuntimeError):
    pass


def configured_models() -> list[str]:
    raw = os.getenv("KMJ_OPENCODE_FREE_MODELS", "").strip()
    values = [item.strip() for item in raw.split(",") if item.strip()] if raw else DEFAULT_MODELS
    models = []
    for value in values:
        if value.startswith("opencode/") and value not in models:
            models.append(value)
    return models or DEFAULT_MODELS.copy()


def verify_zero_price(payload: str) -> None:
    try:
        cost = tomllib.loads(payload)["cost"]
        for key in ("input", "output"):
            value = cost[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != 0:
                raise ValueError("nonzero or unknown price")
        for key in ("cache_read", "cache_write"):
            if key not in cost:
                continue
            value = cost[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != 0:
                raise ValueError("nonzero cache price")
    except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise OpenCodeUnavailable("OPENCODE_COST_NOT_VERIFIED_ZERO") from exc


def check_price(model: str) -> None:
    slug = model.removeprefix("opencode/")
    url = f"{PRICE_ROOT}/{slug}.toml"
    try:
        with urllib.request.urlopen(url, timeout=12) as response:
            payload = response.read(32000).decode("utf-8")
        verify_zero_price(payload)
    except OpenCodeUnavailable:
        raise
    except Exception as exc:
        raise OpenCodeUnavailable("OPENCODE_PRICE_SOURCE_UNAVAILABLE") from exc


def parse_completion(output: str) -> str:
    pieces = []
    finishes = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        part = event.get("part", {})
        if event.get("type") == "error":
            raise OpenCodeUnavailable("OPENCODE_COMPLETION_FAILED")
        if not isinstance(part, dict):
            continue
        if event.get("type") == "text" and isinstance(part.get("text"), str):
            pieces.append(part["text"])
        if event.get("type") == "step_finish":
            cost = part.get("cost")
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost != 0:
                raise OpenCodeUnavailable("OPENCODE_RESULT_COST_NOT_ZERO")
            finishes.append(part.get("reason"))
    content = "".join(pieces).strip()
    if not content or not finishes or finishes[-1] != "stop":
        raise OpenCodeUnavailable("OPENCODE_COMPLETION_INCOMPLETE")
    return content


def isolated_environment(directory: Path, model: str) -> dict[str, str]:
    allowed = {"PATH", "LANG", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.update({
        "XDG_CONFIG_HOME": str(directory / "config"),
        "XDG_DATA_HOME": str(directory / "data"),
        "XDG_CACHE_HOME": str(directory / "cache"),
        "OPENCODE_CONFIG_DIR": str(directory / "config/opencode"),
        "OPENCODE_DISABLE_AUTOUPDATE": "true",
        "OPENCODE_DISABLE_DEFAULT_PLUGINS": "true",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "true",
        "OPENCODE_DISABLE_CLAUDE_CODE": "true",
        "OPENCODE_CONFIG_CONTENT": json.dumps({
            "model": model,
            "small_model": model,
            "enabled_providers": ["opencode"],
            "share": "disabled",
            "autoupdate": False,
            "permission": {"*": "deny"},
            "agent": {"build": {
                "prompt": "You are a text-only assistant. Use only the context provided in the request. "
                "Return the requested answer and exactly the requested output format. "
                "Do not inspect files, execute commands, delegate, or use tools. "
                "When JSON is requested, output one valid JSON object with escaped string newlines and no surrounding prose.",
                "permission": {"*": "deny"},
            }},
        }),
    })
    return env


def _attempt_model(binary: str, model: str, prompt: str, timeout: int) -> tuple[str, float]:
    check_price(model)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="kmj-free-client-") as directory:
        root = Path(directory)
        result = subprocess.run(
            [binary, "--pure", "run", "--format", "json", "--model", model, prompt],
            cwd=root,
            env=isolated_environment(root, model),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    if result.returncode != 0:
        raise OpenCodeUnavailable("OPENCODE_CLIENT_FAILED")
    return parse_completion(result.stdout), round((time.monotonic() - started) * 1000, 1)


def complete(messages: list[dict[str, str]]) -> dict:
    binary = os.getenv("KMJ_OPENCODE_BINARY", "")
    if os.getenv("KMJ_OPENCODE_FREE_ENABLED") != "true" or not Path(binary).is_file():
        raise OpenCodeUnavailable("OPENCODE_CLIENT_NOT_CONFIGURED")
    prompt = "\n\n".join(f"{message['role'].upper()}:\n{message['content']}" for message in messages)
    if len(prompt.encode()) > 64000:
        raise OpenCodeUnavailable("OPENCODE_PROMPT_TOO_LARGE")

    timeout = max(10, min(int(os.getenv("KMJ_OPENCODE_MODEL_TIMEOUT_SECONDS", "55")), 180))
    attempts = []
    last_error: Exception | None = None
    for model in configured_models():
        try:
            content, latency = _attempt_model(binary, model, prompt, timeout)
            attempts.append({"provider": "opencode-client", "model": model, "result": "success"})
            proof_path = os.getenv("KMJ_AI_PROOF_PATH")
            if proof_path:
                proof = {
                    "provider": "opencode-client",
                    "model": model,
                    "status": "verified",
                    "cost": 0,
                    "verified_at": int(time.time()),
                    "latency_ms": latency,
                }
                target = Path(proof_path)
                temporary = target.with_suffix(".tmp")
                temporary.write_text(json.dumps(proof), encoding="utf-8")
                temporary.replace(target)
            return {
                "model": model,
                "provider": "opencode-client",
                "verification": "fresh-official-zero-price-and-zero-cost-completion",
                "attempts": attempts,
                "response": {"choices": [{"message": {"content": content}}]},
            }
        except (OpenCodeUnavailable, OSError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            attempts.append({"provider": "opencode-client", "model": model, "result": "failed"})
            continue
    raise OpenCodeUnavailable("OPENCODE_ALL_VERIFIED_FREE_MODELS_UNAVAILABLE") from last_error


def probe_zero_cost_route(
    completion_client: Callable[[list[dict[str, str]]], dict] = complete,
    *,
    max_attempts: int = 2,
) -> dict:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    messages = [{
        "role": "user",
        "content": 'Return exactly one JSON object: {"marker":"KMJ_FREE_ROUTE_OK"}. No tools or prose.',
    }]
    for _attempt in range(1, max_attempts + 1):
        response = completion_client(messages)
        try:
            answer = response["response"]["choices"][0]["message"]["content"]
            marker = json.loads(answer).get("marker")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            marker = None
        if marker == "KMJ_FREE_ROUTE_OK":
            return response
    raise OpenCodeUnavailable("OPENCODE_PROBE_FORMAT_INVALID")


if __name__ == "__main__":
    response = probe_zero_cost_route()
    print(json.dumps({
        "provider": response["provider"],
        "model": response["model"],
        "cost": 0,
        "result": "PASS",
    }))
