"""Build the exact Nginx /login release evidence map; never activate a release."""
import re

SHA = re.compile(r"[0-9a-f]{40}\Z")
ROOT = "/home/kmjprod/releases/platform-"
SUFFIX = "/apps/platform/public:/login$"
START = 'map "$realpath_root:$request_uri" $kmj_production_release_sha {\n    default "";\n'
END = "}\n"

def render(shas):
    """A verified current + candidate pair preserves evidence across rollback."""
    values = tuple(shas)
    if not 1 <= len(values) <= 2 or any(
            not isinstance(s, str) or not SHA.fullmatch(s) for s in values):
        raise ValueError("BLOCKED_MAP_SHA")
    if len(set(values)) != len(values) or len({s[:12] for s in values}) != len(values):
        raise ValueError("BLOCKED_MAP_COLLISION")
    return START + "".join(
        "    ~^" + ROOT + s[:12] + SUFFIX + " " + s + ";\n"
        for s in sorted(values)
    ) + END

def parse_existing(data):
    """Reject unrecognized rules, wrong prefixes, duplicates, or broad paths."""
    if not isinstance(data, str) or len(data) > 1024:
        raise ValueError("BLOCKED_MAP_FORMAT")
    if not data.startswith(START) or not data.endswith(END):
        raise ValueError("BLOCKED_MAP_FORMAT")
    lines = data[len(START):-len(END)].splitlines()
    pattern = re.compile(
        r"    ~\^" + re.escape(ROOT) + r"([0-9a-f]{12})"
        + re.escape(SUFFIX) + r" ([0-9a-f]{40});\Z"
    )
    values = []
    for line in lines:
        match = pattern.fullmatch(line)
        if not match or match[1] != match[2][:12]:
            raise ValueError("BLOCKED_MAP_IDENTITY")
        values.append(match[2])
    if render(values) != data:
        raise ValueError("BLOCKED_MAP_FORMAT")
    return tuple(values)

def plan(existing, current_sha, candidate_sha, verify):
    """The caller supplies the existing privileged exact Git verifier.

    Never trust a 12-character directory name or a stale mapping alone.
    Only return a proposed map; the reviewed prepare/activation caller owns
    the lock, root file validation, config transaction, reload and live probes.
    """
    values = (current_sha,) if current_sha == candidate_sha else (current_sha, candidate_sha)
    proposed = render(values)
    old = parse_existing(existing)
    if current_sha not in old:
        raise ValueError("BLOCKED_CURRENT_MAP_MISSING")
    for sha in values:
        if verify(sha) != sha:
            raise ValueError("BLOCKED_MAP_UNVERIFIED_RELEASE")
    return proposed
