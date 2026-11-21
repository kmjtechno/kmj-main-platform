#!/usr/bin/env python3
"""Strict independent P520 offsite restore receipt verifier, read-only.

A signature proves attribution to an owner-pinned P520 signing key, not that
a restore actually happened; owner must cross-examine raw host evidence.
This tool grants NO production approval and is not an autopublish bypass.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

CANDIDATE = "4c9d59103b99a6cfe675bb7b8961fc956eb294f0"
PREDECESSOR = "platform-ce6ad7dc9d89"
HEX = re.compile(r"[a-f0-9]{64}\Z")
EXPECTED = {
    "schema", "receiver", "receiverHost", "candidateSha", "expectedCurrentRelease",
    "encryptedSha256", "sourceLocalSha256", "receivedCipherSha256",
    "receivedCipherBytes", "decryptVerified", "bundleManifestVerified",
    "isolatedPostgresRestoreVerified", "restoredStorageParityVerified",
    "networkIsolationVerified", "productionDatabaseUnchanged", "completedAtUtc",
}
BOOLEANS = {
    "decryptVerified", "bundleManifestVerified", "isolatedPostgresRestoreVerified",
    "restoredStorageParityVerified", "networkIsolationVerified",
    "productionDatabaseUnchanged",
}
MAX_BYTES = 16384
MAX_FUTURE = timedelta(minutes=5)
MAX_AGE = timedelta(hours=48)


class Block(Exception):
    pass


def unique(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise Block("DUPLICATE_JSON_KEY")
        obj[k] = v
    return obj


def read_regular(path: Path, max_size: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                not 1 <= info.st_size <= max_size):
            raise Block("UNTRUSTED_FILE")
        chunks = []
        left = info.st_size
        while left:
            piece = os.read(fd, min(left, 8192))
            if not piece:
                raise Block("TRUNCATED_FILE")
            chunks.append(piece)
            left -= len(piece)
        if os.read(fd, 1):
            raise Block("FILE_GREW")
        return b"".join(chunks)
    finally:
        os.close(fd)


def verify(receipt_bytes: bytes, signature: bytes, public_key_pem: bytes,
           expected_pubkey_sha: str, encrypted_sha: str, source_sha: str,
           now: datetime | None = None) -> dict:
    if not all(HEX.fullmatch(v) for v in (expected_pubkey_sha, encrypted_sha, source_sha)):
        raise Block("UNPINNED_DIGEST_ARGUMENT")
    if hashlib.sha256(public_key_pem).hexdigest() != expected_pubkey_sha:
        raise Block("UNTRUSTED_PUBLIC_KEY")
    if len(signature) != 64 or len(receipt_bytes) > MAX_BYTES:
        raise Block("BAD_SIGNATURE_OR_RECEIPT_SIZE")
    try:
        o = json.loads(receipt_bytes.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(Block("JSON_NONFINITE")))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise Block("RECEIPT_JSON_INVALID") from exc
    if not isinstance(o, dict) or set(o) != EXPECTED:
        raise Block("RECEIPT_SCHEMA")
    if (o["schema"] != "kmj.independent-offsite.restore.v1" or
        o["receiver"] != "p520" or
        o["receiverHost"] != "DESKTOP-5FVJMET" or
        o["candidateSha"] != CANDIDATE or
        o["expectedCurrentRelease"] != PREDECESSOR or
        o["encryptedSha256"] != encrypted_sha or
        o["sourceLocalSha256"] != source_sha or
        o["receivedCipherSha256"] != encrypted_sha):
        raise Block("RECOVERY_IDENTITY_OR_DIGEST")
    if (type(o["receivedCipherBytes"]) is not int or
            not 256 <= o["receivedCipherBytes"] <= 10 * 1024**3):
        raise Block("CIPHER_BYTES_INVALID")
    if any(o[k] is not True for k in BOOLEANS):
        raise Block("RECOVERY_PROOF_FLAGS")
    try:
        stamp = datetime.fromisoformat(o["completedAtUtc"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise Block("RECEIPT_TIMESTAMP") from exc
    if stamp.tzinfo is None:
        raise Block("UNZONED_TIMESTAMP")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = now - stamp.astimezone(timezone.utc)
    if age < -MAX_FUTURE or age > MAX_AGE:
        raise Block("RECEIPT_STALE_OR_FUTURE")
    # Verify the exact bytes; never accept a JSON rewrite after signing.
    with __import__("tempfile").TemporaryDirectory(prefix="kmj-p520-sig-") as d:
        receipt_file = Path(d) / "receipt"
        signature_file = Path(d) / "signature"
        key_file = Path(d) / "public.pem"
        for target, data in ((receipt_file, receipt_bytes),
                             (signature_file, signature),
                             (key_file, public_key_pem)):
            with open(target, "xb") as f:
                f.write(data)
            target.chmod(0o600)
        try:
            result = subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-pubin", "-rawin",
                 "-inkey", str(key_file), "-sigfile", str(signature_file),
                 "-in", str(receipt_file)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=15)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise Block("ED25519_ENGINE_UNAVAILABLE") from exc
    if result.returncode != 0:
        raise Block("ED25519_SIGNATURE_INVALID")
    return {
        "receiptCrypto": "PASS",
        "receiver": "p520",
        "candidateSha": CANDIDATE,
        "encryptedSha256": encrypted_sha,
        "sourceLocalSha256": source_sha,
        "productionApproval": "NOT_GRANTED",
        "independentOperatorReview": "REQUIRED",
        "googleVpsDependency": "NONE_IN_VERIFIER",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--owner-pinned-public-key", type=Path, required=True)
    parser.add_argument("--expected-key-sha256", required=True)
    parser.add_argument("--encrypted-sha256", required=True)
    parser.add_argument("--source-local-sha256", required=True)
    opts = parser.parse_args(argv)
    try:
        receipt = read_regular(opts.receipt, MAX_BYTES)
        sig = read_regular(opts.signature, 64)
        key = read_regular(opts.owner_pinned_public_key, 4096)
        result = verify(receipt, sig, key, opts.expected_key_sha256,
                        opts.encrypted_sha256, opts.source_local_sha256)
    except (Block, OSError) as exc:
        code = str(exc) if isinstance(exc, Block) else "READ_ERROR"
        if not re.fullmatch(r"[A-Z0-9_]{3,70}", code):
            code = "UNCLASSIFIED"
        print("KMJ_P520_RECEIPT=BLOCKED_" + code)
        print("PRODUCTION_APPROVAL=NOT_GRANTED")
        return 2
    print("KMJ_P520_RECEIPT=CRYPTO_VALIDATED")
    print("RECOVERY_HOST=" + result["receiver"])
    print("CANDIDATE_SHA=" + result["candidateSha"])
    print("INDEPENDENT_OPERATOR_REVIEW=REQUIRED")
    print("PRODUCTION_APPROVAL=NOT_GRANTED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
