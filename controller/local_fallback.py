"""Authenticated loopback-only CPU inference; never a ranked cloud provider."""
from __future__ import annotations

import asyncio
import fcntl
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class LocalFallbackUnavailable(RuntimeError):
    pass


def enabled() -> bool:
    return os.getenv("KMJ_LOCAL_FALLBACK_ENABLED") == "true"


def settings() -> dict:
    if not enabled():
        raise LocalFallbackUnavailable("LOCAL_FALLBACK_DISABLED")
    url = os.getenv("KMJ_LOCAL_FALLBACK_BASE_URL", "http://127.0.0.1:18766/v1").rstrip("/")
    key = os.getenv("KMJ_LOCAL_FALLBACK_API_KEY", "").strip()
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "http" and ipaddress.ip_address(parsed.hostname or "").is_loopback
                 and parsed.path == "/v1" and not parsed.query and not parsed.fragment
                 and parsed.username is None and parsed.password is None and parsed.port is not None)
        context = int(os.getenv("KMJ_LOCAL_FALLBACK_CONTEXT_TOKENS", "8192"))
        output = int(os.getenv("KMJ_LOCAL_FALLBACK_MAX_OUTPUT_TOKENS", "1024"))
        timeout = int(os.getenv("KMJ_LOCAL_FALLBACK_TIMEOUT_SECONDS", "120"))
        if not valid or not key or not 1024 <= context <= 32768 or not 1 <= output <= 4096 or output >= context or not 10 <= timeout <= 180:
            raise ValueError()
    except ValueError as exc:
        raise LocalFallbackUnavailable("LOCAL_FALLBACK_CONFIG_INVALID") from exc
    return {"url":url, "origin":url[:-3], "key":key, "context":context, "output":output,
            "timeout":timeout, "model":os.getenv("KMJ_LOCAL_FALLBACK_MODEL", "kmj-emergency-coder")}


def validate_messages(messages: list[dict[str, str]]) -> None:
    if not isinstance(messages, list) or len(messages) > 64:
        raise LocalFallbackUnavailable("REQUEST_INVALID")
    total = 0
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant"} or not isinstance(message.get("content"), str):
            raise LocalFallbackUnavailable("REQUEST_INVALID")
        total += len(message["content"].encode("utf-8"))
    if total > 65536:
        raise LocalFallbackUnavailable("REQUEST_TOO_LARGE")


async def complete(messages: list[dict[str, str]], temperature: float = 0.1) -> dict:
    validate_messages(messages)
    config = settings()
    # Cross-process bound: controller and worker cannot overload a single CPU slot.
    lock_path = Path(os.getenv("KMJ_LOCAL_FALLBACK_LOCK_PATH", str(Path.home() / ".kmj/local-fallback.lock")))
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LocalFallbackUnavailable("LOCAL_FALLBACK_BUSY") from exc
        async with asyncio.timeout(config["timeout"]):
            async with httpx.AsyncClient(timeout=httpx.Timeout(config["timeout"], connect=3), trust_env=False, follow_redirects=False) as client:
                headers = {"Authorization":f"Bearer {config['key']}", "Content-Type":"application/json"}
                template = await client.post(config["origin"] + "/apply-template", headers=headers,
                                             json={"messages":messages, "add_generation_prompt":True})
                template.raise_for_status()
                prompt = template.json().get("prompt")
                if not isinstance(prompt, str):
                    raise LocalFallbackUnavailable("LOCAL_TEMPLATE_INVALID")
                tokens_response = await client.post(config["origin"] + "/tokenize", headers=headers,
                                                    json={"content":prompt, "add_special":False})
                tokens_response.raise_for_status()
                tokens = tokens_response.json().get("tokens")
                if not isinstance(tokens, list) or not all(type(token) is int for token in tokens):
                    raise LocalFallbackUnavailable("LOCAL_TOKEN_COUNT_INVALID")
                if len(tokens) + config["output"] + 32 > config["context"]:
                    raise LocalFallbackUnavailable("LOCAL_CONTEXT_EXCEEDED")
                response = await client.post(config["url"] + "/chat/completions", headers=headers,
                    json={"model":config["model"], "messages":messages, "temperature":temperature,
                          "max_tokens":config["output"], "stream":False, "cache_prompt":False})
                response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices", [])
                if not choices or choices[0].get("finish_reason") != "stop" or not isinstance(choices[0].get("message", {}).get("content"), str) or not choices[0]["message"]["content"].strip():
                    raise LocalFallbackUnavailable("LOCAL_COMPLETION_INCOMPLETE")
                return {"model":config["model"], "provider":"cpu-local-emergency", "owner":"KMJ",
                        "verification":"owned-cpu-emergency-zero-inference-fee",
                        "attempts":[{"provider":"cpu-local-emergency", "model":config["model"], "result":"success"}],
                        "response":payload}
    except LocalFallbackUnavailable:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
        raise LocalFallbackUnavailable("LOCAL_FALLBACK_UNAVAILABLE") from exc
    finally:
        os.close(fd)
