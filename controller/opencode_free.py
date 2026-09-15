"""Use the official OpenCode client with a freshly verified zero-cost model."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib
import urllib.request

MODEL = "opencode/big-pickle"
PRICE_URL = "https://raw.githubusercontent.com/anomalyco/models.dev/dev/providers/opencode/models/big-pickle.toml"


class OpenCodeUnavailable(RuntimeError):
    pass


def verify_zero_price(payload: str) -> None:
    try:
        cost = tomllib.loads(payload)["cost"]
        for key in ("input", "output", "cache_read", "cache_write"):
            value = cost[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value != 0:
                raise ValueError("nonzero or unknown price")
    except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise OpenCodeUnavailable("OPENCODE_COST_NOT_VERIFIED_ZERO") from exc


def check_price() -> None:
    try:
        with urllib.request.urlopen(PRICE_URL, timeout=12) as response:
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


def isolated_environment(directory: Path) -> dict[str, str]:
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
            "model": MODEL,
            "small_model": MODEL,
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


def complete(messages: list[dict[str, str]]) -> dict:
    binary = os.getenv("KMJ_OPENCODE_BINARY", "")
    if os.getenv("KMJ_OPENCODE_FREE_ENABLED") != "true" or not Path(binary).is_file():
        raise OpenCodeUnavailable("OPENCODE_CLIENT_NOT_CONFIGURED")
    prompt = "\n\n".join(f"{message['role'].upper()}:\n{message['content']}" for message in messages)
    if len(prompt.encode()) > 64000:
        raise OpenCodeUnavailable("OPENCODE_PROMPT_TOO_LARGE")
    check_price()
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="kmj-free-client-") as directory:
            root = Path(directory)
            result = subprocess.run(
                [binary, "--pure", "run", "--format", "json", "--model", MODEL, prompt],
                cwd=root, env=isolated_environment(root), text=True, capture_output=True, timeout=180,
            )
        if result.returncode != 0:
            raise OpenCodeUnavailable("OPENCODE_CLIENT_FAILED")
        content = parse_completion(result.stdout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OpenCodeUnavailable("OPENCODE_CLIENT_UNAVAILABLE") from exc

    latency = round((time.monotonic() - started) * 1000, 1)
    proof_path = os.getenv("KMJ_AI_PROOF_PATH")
    if proof_path:
        proof = {
            "provider": "opencode-client", "model": MODEL, "status": "verified",
            "cost": 0, "verified_at": int(time.time()), "latency_ms": latency,
        }
        target = Path(proof_path)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(proof), encoding="utf-8")
        temporary.replace(target)
    return {
        "model": MODEL, "provider": "opencode-client",
        "verification": "fresh-official-zero-price-and-zero-cost-completion",
        "attempts": [{"provider": "opencode-client", "model": MODEL, "result": "success"}],
        "response": {"choices": [{"message": {"content": content}}]},
    }


if __name__ == "__main__":
    response = complete([{"role": "user", "content": 'Return exactly one JSON object: {"marker":"KMJ_FREE_ROUTE_OK"}. No tools or prose.' }])
    answer = response["response"]["choices"][0]["message"]["content"]
    if json.loads(answer).get("marker") != "KMJ_FREE_ROUTE_OK":
        raise SystemExit("OpenCode probe marker did not match")
    print(json.dumps({"provider": response["provider"], "model": MODEL, "cost": 0, "result": "PASS"}))
