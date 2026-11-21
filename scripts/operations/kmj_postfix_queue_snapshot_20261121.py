#!/usr/bin/env python3
"""Secret-free, read-only aggregate from Postfix postqueue -j JSON lines.

This program NEVER opens Postfix mail files, changes a queue, or sends mail.
For P0 operations: sudo postqueue -j | python3 kmj_postfix_queue_snapshot_20261121.py
"""
import collections
import datetime as dt
import json
import math
import re
import sys
import time
from typing import Any, Iterable

SCHEMA_VERSION = 1
MAX_MESSAGES = 100000
MAX_LINE_BYTES = 1024 * 1024
CURRENT_ELITE_LIFETIME_HOURS = 120  # Owner measured maximal_queue_lifetime=5d.
ERROR_CODE = re.compile(r"(?<!\d)(525|535|530|454|450)(?!\d)")
QUEUE_TYPES = frozenset({"active", "deferred", "hold", "incoming", "maildrop", "corrupt"})

def _age_bucket(hours: float) -> str:
    if hours >= CURRENT_ELITE_LIFETIME_HOURS:
        return "AT_OR_OVER_120H"
    if hours >= 96:
        return "96_TO_UNDER_120H"
    if hours >= 24:
        return "24_TO_UNDER_96H"
    return "UNDER_24H"

def _delay_category(reason: str) -> str:
    lower = reason.lower()
    code = ERROR_CODE.search(lower)
    if code is not None:
        return "SMTP_" + code.group(1)
    if "authentication failed" in lower or "sasl" in lower:
        return "SMTP_AUTH_OTHER"
    if "timeout" in lower or "timed out" in lower:
        return "TIMEOUT"
    if "connection refused" in lower:
        return "CONNECTION_REFUSED"
    if "network is unreachable" in lower:
        return "NETWORK_UNREACHABLE"
    if "host not found" in lower or "name service" in lower:
        return "DNS"
    if "tls" in lower or "certificate" in lower:
        return "TLS"
    if not lower.strip():
        return "NO_RECORDED_DELAY"
    return "OTHER_REDACTED"

def snapshot(stream: Iterable[str], *, now: float) -> dict[str, Any]:
    """Parse queue records and emit only categories, never identity/message data."""
    if not math.isfinite(now) or now <= 0:
        raise ValueError("INVALID_NOW")
    messages = 0
    recipients = 0
    queue_states: collections.Counter[str] = collections.Counter()
    age_buckets: collections.Counter[str] = collections.Counter()
    delay_categories: collections.Counter[str] = collections.Counter()
    unknown_age = 0
    future_arrival = 0
    oldest_hours: float | None = None

    for line in stream:
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            raise ValueError("QUEUE_RECORD_TOO_LARGE")
        if not line.strip():
            continue
        messages += 1
        if messages > MAX_MESSAGES:
            raise ValueError("QUEUE_RECORD_LIMIT")
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError("INVALID_QUEUE_JSON") from None
        if not isinstance(item, dict):
            raise ValueError("INVALID_QUEUE_OBJECT")

        name = item.get("queue_name")
        name = name if isinstance(name, str) and name in QUEUE_TYPES else "unknown"
        queue_states[name] += 1
        arrival = item.get("arrival_time")
        if isinstance(arrival, (int, float)) and not isinstance(arrival, bool) and math.isfinite(arrival) and arrival > 0:
            difference = now - arrival
            if difference < -60:
                future_arrival += 1
                unknown_age += 1
            else:
                hours = max(0.0, difference / 3600)
                oldest_hours = hours if oldest_hours is None else max(oldest_hours, hours)
                age_buckets[_age_bucket(hours)] += 1
        else:
            unknown_age += 1

        recips = item.get("recipients", [])
        if not isinstance(recips, list):
            raise ValueError("INVALID_RECIPIENTS_ARRAY")
        recipients += len(recips)
        for recipient in recips:
            if not isinstance(recipient, dict):
                raise ValueError("INVALID_RECIPIENT_OBJECT")
            reason = recipient.get("delay_reason", "")
            delay_categories[_delay_category(reason if isinstance(reason, str) else "")] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "source": "postqueue_json_stdin",
        "captured_at_utc": dt.datetime.fromtimestamp(now, tz=dt.timezone.utc).isoformat(),
        "queue_messages": messages,
        "queue_recipients": recipients,
        "queue_states": dict(sorted(queue_states.items())),
        "age_buckets": dict(sorted(age_buckets.items())),
        "unknown_age_messages": unknown_age,
        "future_arrival_messages": future_arrival,
        "oldest_message_hours": round(oldest_hours, 1) if oldest_hours is not None else None,
        "last_recorded_delay_categories": dict(sorted(delay_categories.items())),
        "observed_lifetime_threshold_hours": CURRENT_ELITE_LIFETIME_HOURS,
        "queue_drained": messages == 0,
        "recipient_delivery_proven": False,
        "queue_mutation": "NONE",
    }

def main() -> int:
    try:
        result = snapshot(sys.stdin, now=time.time())
    except (ValueError, UnicodeError, OSError):
        print("KMJ_MAIL_SNAPSHOT=INVALID_INPUT", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
