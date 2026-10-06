#!/usr/bin/env bash
# Zero-cost CI readiness: no network, no installation, no secrets or mutations.
set -euo pipefail

echo "KMJ Main Platform — dedicated test VM CI preflight"
echo "This check is read-only. Do not run CI on your production VPS."
failures=0

check_command() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "PASS command=$name"
  else
    echo "MISSING command=$name"
    failures=$((failures + 1))
  fi
}

for cmd in bash curl git tar sha256sum python3 php composer node npm cargo rustup runuser systemctl; do
  check_command "$cmd"
done

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  echo "OS=${PRETTY_NAME:-unknown}"
fi
echo "CPU_count=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo unavailable)"

mem_kb="$(awk '/^MemAvailable:/{print $2}' /proc/meminfo 2>/dev/null || true)"
if [[ "${mem_kb:-0}" =~ ^[0-9]+$ ]]; then
  echo "available_memory_MiB=$((mem_kb / 1024))"
  if (( mem_kb < 3 * 1024 * 1024 )); then
    echo "WARNING memory below 3 GiB; parallel PHP/JS + Rust verification may need a larger test VM"
  fi
fi

if [[ -d /opt/kmj-actions-runner ]]; then
  if [[ -f /opt/kmj-actions-runner/.runner ]]; then
    echo "Existing runner registration detected (no changes made)"
  else
    echo "Runner installation directory exists but no registration is present"
  fi
fi

if command -v systemctl >/dev/null 2>&1; then
  service="$(systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '/actions.runner.*kmj-main-platform/{print $1;exit}' || true)"
  if [[ -n "$service" ]]; then
    echo "Runner service detected: $service"
    echo "Runner service active=$(systemctl is-active "$service" 2>/dev/null || true)"
  fi
fi

if (( failures > 0 )); then
  echo "Preflight needs ${failures} missing tools. Do not claim CI green."
  exit 1
fi
echo "Preflight toolchain present. This is NOT proof of GitHub registration or CI success."
