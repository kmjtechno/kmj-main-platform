#!/usr/bin/env python3
"""Verify the public staging monitor and optional exact deployment SHA."""
import json
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

origin = 'https://staging.kmjtechno.com'
expected_sha = sys.argv[1] if len(sys.argv) == 2 else None
if expected_sha is not None and re.fullmatch(r'[0-9a-f]{40}', expected_sha) is None:
    raise SystemExit('Expected deployment SHA must be a full commit SHA')


def read_json(path, headers=None):
    headers = headers or {'Accept': 'application/json'}
    request = Request(origin + path, headers=headers)
    try:
        response = urlopen(request, timeout=20)
    except HTTPError as error:
        # Inertia requires the deployed asset version for protocol requests.
        # Accept one same-URL version handshake, never an arbitrary redirect.
        version = error.headers.get('X-Inertia-Version')
        if (
            path != '/info' or error.code != 409 or not version
            or error.headers.get('X-Inertia-Location') != origin + path
        ):
            raise
        error.close()
        request = Request(origin + path, headers={**headers, 'X-Inertia-Version': version})
        response = urlopen(request, timeout=20)
    with response:
        if response.status != 200 or response.geturl() != origin + path:
            raise SystemExit('Unexpected staging status or redirect: ' + path)
        return json.load(response)


page = read_json('/info', {
    'X-Inertia': 'true',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'text/html, application/xhtml+xml',
})
if page.get('component') != 'info' or page.get('props', {}).get('pollIntervalMs') != 5000:
    raise SystemExit('The staging URL did not return the live monitor component')

status = read_json('/info/status')
if status.get('runtime', {}).get('application') is not True:
    raise SystemExit('The staging application probe is not healthy')
deployed = status.get('deployment', {}).get('deployed_sha')
if expected_sha is not None and deployed != expected_sha:
    raise SystemExit(f'Public deployed SHA mismatch: expected {expected_sha}, got {deployed}')

print(json.dumps({
    'monitor_component': page['component'],
    'status': status.get('status'),
    'database': status.get('runtime', {}).get('database'),
    'deployed_sha': deployed,
    'ai_recently_verified': status.get('runtime', {}).get('ai_router_online'),
    'ai_last_verified_at': status.get('runtime', {}).get('ai_last_verified_at'),
    'expected_sha': expected_sha,
    'result': 'PASS',
}))
