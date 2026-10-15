"""KMJ KSLP first-use device registration reference (not a lease verifier).

Requires no third-party Python packages. The caller must supply its stable
Ed25519 keypair via a secure OS keystore/TPM-backed signer. This module neither
creates nor persists secrets, and deliberately NEVER unlocks paid features.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit
from uuid import uuid4


class ActivationError(Exception):
    """A bounded activation error that never contains credentials."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(data) > 4096:
        raise ActivationError("REQUEST_TOO_LARGE")
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise ActivationError("ACTIVATION_HTTP_FAILED")
            if response.headers.get_content_type() != "application/json":
                raise ActivationError("ACTIVATION_RESPONSE_INVALID")
            body = response.read(4097)
            if len(body) > 4096:
                raise ActivationError("ACTIVATION_RESPONSE_TOO_LARGE")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ActivationError("ACTIVATION_UNAVAILABLE_OR_DENIED") from None
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ActivationError("ACTIVATION_RESPONSE_INVALID") from None
    if not isinstance(parsed, dict):
        raise ActivationError("ACTIVATION_RESPONSE_INVALID")
    return parsed


@dataclass(frozen=True)
class DeviceReceipt:
    activation_id: str
    product: str
    device_registered: bool
    signed_lease_issued: bool

    @property
    def grants_entitlement(self) -> bool:
        # Registration is never a signed offline license. A separate verified
        # KSLP lease verifier is required before granting product features.
        return False


def register_device(
    *,
    license_key: str,
    product: str,
    device_public_key: bytes,
    machine_hash: str,
    sign: Callable[[bytes], bytes],
    base_url: str = "https://kmjtechno.com",
    metadata_consent: bool = False,
    platform: str | None = None,
    app_version: str | None = None,
    post: Callable[[str, dict], dict] = _post_json,
) -> DeviceReceipt:
    """Complete challenge and PoP registration without storing a bootstrap key.

    'sign' must be a caller-owned Ed25519 detached signer whose stable private
    key lives in an approved keychain/TPM. Never send the private key to KSLP.
    """
    try:
        parts = urlsplit(base_url)
        allowed_origin = (
            parts.scheme == "https"
            and parts.hostname is not None
            and parts.hostname.lower() == "kmjtechno.com"
            and not parts.username
            and not parts.password
            and not parts.query
            and not parts.fragment
            and parts.path in ("", "/")
            and parts.port in (None, 443)
        )
    except ValueError:
        allowed_origin = False
    if not allowed_origin:
        raise ActivationError("KSLP_HTTPS_ORIGIN_REQUIRED")
    if not re.fullmatch(r"KMJ1-[A-Za-z0-9_-]{43}", license_key):
        raise ActivationError("LICENSE_KEY_FORMAT_INVALID")
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.:-]{2,63}", product):
        raise ActivationError("PRODUCT_INVALID")
    if not isinstance(device_public_key, bytes) or len(device_public_key) != 32:
        raise ActivationError("ED25519_PUBLIC_KEY_REQUIRED")
    if not re.fullmatch(r"[a-f0-9]{64}", machine_hash):
        raise ActivationError("MACHINE_HASH_INVALID")
    if platform is not None and platform not in {
        "windows", "linux", "macos", "android", "ios", "other"
    }:
        raise ActivationError("PLATFORM_INVALID")
    if app_version is not None and len(app_version) > 64:
        raise ActivationError("APP_VERSION_INVALID")
    if not isinstance(metadata_consent, bool):
        raise ActivationError("CONSENT_INVALID")
    origin = base_url.rstrip("/")
    identity = "ed25519:" + _b64u(device_public_key)
    challenge = post(origin + "/api/v1/kslp/developer/activation/challenge", {
        "license_key": license_key,
        "server_identity": identity,
    })
    license_id = challenge.get("license_id")
    nonce = challenge.get("nonce")
    challenge_id = challenge.get("challenge_id")
    if (
        not isinstance(license_id, str)
        or not re.fullmatch(r"[0-9a-fA-F-]{36}", license_id)
        or not isinstance(challenge_id, str)
        or not re.fullmatch(r"[0-9a-fA-F-]{36}", challenge_id)
        or not isinstance(nonce, str) or not 32 <= len(nonce) <= 128
        or challenge.get("product") != product
    ):
        raise ActivationError("CHALLENGE_RESPONSE_INVALID")
    message = ("KSLP-ACTIVATE-v1|" + license_id + "|" + nonce).encode("utf-8")
    signature = sign(message)
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise ActivationError("ED25519_SIGNATURE_INVALID")
    result = post(origin + "/api/v1/kslp/developer/activation/complete", {
        "license_key": license_key,
        "server_identity": identity,
        "machine_hash": machine_hash,
        "request_id": str(uuid4()),
        "challenge_id": challenge_id,
        "nonce": nonce,
        "signature": _b64u(signature),
        "metadata_consent": metadata_consent,
        "platform": platform if metadata_consent else None,
        "app_version": app_version if metadata_consent else None,
    })
    if (
        result.get("product") != product
        or result.get("device_registered") is not True
        or result.get("signed_lease_issued") is not False
        or not isinstance(result.get("activation_id"), str)
        or not re.fullmatch(r"[0-9a-fA-F-]{36}", result["activation_id"])
    ):
        raise ActivationError("UNEXPECTED_ACTIVATION_STATE")
    return DeviceReceipt(result["activation_id"], product, True, False)
