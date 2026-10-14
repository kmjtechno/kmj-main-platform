#!/usr/bin/env python3
"""KMJ Mail: idempotently publish ONLY the prepared public DKIM TXT via a scoped Cloudflare token.

No Laravel/SMTP changes; never prints or sends private key or Cloudflare token.
Run only on owner-approved host with a restricted Zone DNS Edit token in a root-only file.
"""
import argparse
import base64
import json
import os
import pathlib
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DOMAIN = "kmjtechno.com"
SELECTOR = "kmj2026"
RECORD = f"{SELECTOR}._domainkey.{DOMAIN}"
KEYFILE = pathlib.Path("/etc/opendkim/keys/kmjtechno.com/kmj2026.private")
TOKENFILE = pathlib.Path("/etc/kmj-mail/cloudflare-dns.token")
API = "https://api.cloudflare.com/client/v4/"


def fail(reason):
    print("DKIM_CLOUDFLARE=" + reason, flush=True)
    raise SystemExit(2)


def require_private_file(path):
    if path.is_symlink() or not path.is_file():
        fail("BLOCKED_MISSING_OR_LINKED_FILE")
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        fail("BLOCKED_INSECURE_FILE_OWNERSHIP_OR_MODE")


def public_record():
    require_private_file(KEYFILE)
    try:
        raw = subprocess.check_output(
            ["openssl", "pkey", "-in", str(KEYFILE), "-pubout", "-outform", "DER"],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        fail("BLOCKED_KEY_READ")
    return "v=DKIM1; k=rsa; p=" + base64.b64encode(raw).decode("ascii")


def request(method, path, token, data=None):
    url = urllib.parse.urljoin(API, path)
    if urllib.parse.urlparse(url).netloc != "api.cloudflare.com":
        fail("BLOCKED_URL_ORIGIN")
    body = None if data is None else json.dumps(data, separators=(",", ":")).encode()
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read(300000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail("BLOCKED_API_HTTP_" + str(exc.code))
    except (urllib.error.URLError, TimeoutError, ValueError):
        fail("BLOCKED_API_UNAVAILABLE")
    if not isinstance(result, dict) or result.get("success") is not True:
        fail("BLOCKED_API_REJECTED")
    return result.get("result")


def exact_zone(token):
    result = request("GET", "zones?name=" + urllib.parse.quote(DOMAIN), token)
    matches = [zone for zone in (result or []) if zone.get("name") == DOMAIN]
    if len(matches) != 1 or not matches[0].get("id"):
        fail("BLOCKED_NO_UNIQUE_AUTHORIZED_ZONE")
    return matches[0]["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Create missing DKIM TXT, never replace a conflicting record")
    args = parser.parse_args()
    if os.geteuid() != 0:
        fail("BLOCKED_ROOT_REQUIRED")
    value = public_record()
    print("DKIM_LOCAL_PUBLIC_RECORD=READY")
    if not args.apply:
        print("CLOUDFLARE_WRITE=NOT_REQUESTED")
        return
    require_private_file(TOKENFILE)
    token = TOKENFILE.read_text(encoding="utf-8").strip()
    if not token or len(token) < 20 or "\n" in token:
        fail("BLOCKED_INVALID_SCOPED_TOKEN_FILE")
    zone_id = exact_zone(token)
    suffix = "zones/" + urllib.parse.quote(zone_id, safe="") + "/dns_records"
    query = "?type=TXT&name=" + urllib.parse.quote(RECORD, safe="")
    existing = request("GET", suffix + query, token) or []
    # No mutation if a record with this exact name already exists and doesn't match.
    if len(existing) > 1:
        fail("BLOCKED_DUPLICATE_SELECTOR")
    if len(existing) == 1:
        if existing[0].get("type") == "TXT" and existing[0].get("name") == RECORD and existing[0].get("content") == value:
            print("DKIM_CLOUDFLARE=PASS_ALREADY_PUBLISHED")
            return
        fail("BLOCKED_CONFLICTING_DKIM_SELECTOR")
    created = request("POST", suffix, token, {"type": "TXT", "name": RECORD, "content": value, "ttl": 1})
    if not isinstance(created, dict) or created.get("name") != RECORD or created.get("type") != "TXT":
        fail("BLOCKED_API_CREATE_UNCONFIRMED")
    print("DKIM_CLOUDFLARE=PASS_PUBLISHED_PUBLIC_KEY")
    print("DKIM_DNS_PROPAGATION=NOT_VERIFIED")
    print("SMTP_ACTIVATION=NOT_ATTEMPTED")


if __name__ == "__main__":
    main()
