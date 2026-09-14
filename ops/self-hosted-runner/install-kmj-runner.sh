#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_TOKEN:?RUNNER_TOKEN is required}"
REPO_URL="${REPO_URL:-https://github.com/kmjtechno/kmj-main-platform}"
RUNNER_VERSION="${RUNNER_VERSION:-2.328.0}"
RUNNER_USER="${RUNNER_USER:-kmjrunner}"
RUNNER_HOME="${RUNNER_HOME:-/opt/kmj-actions-runner}"
RUNNER_NAME="${RUNNER_NAME:-kmj-main-platform-ci-$(hostname)}"
RUNNER_LABELS="${RUNNER_LABELS:-kmj-main-platform-ci}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root; the runner service itself will use ${RUNNER_USER}." >&2
  exit 1
fi

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git tar libicu-dev

if ! id -u "${RUNNER_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "${RUNNER_USER}"
fi

install -d -o "${RUNNER_USER}" -g "${RUNNER_USER}" "${RUNNER_HOME}"
cd "${RUNNER_HOME}"

archive="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
curl -fsSLo "${archive}" "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${archive}"
tar xzf "${archive}"
rm -f "${archive}"
chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_HOME}"

sudo -u "${RUNNER_USER}" ./config.sh \
  --unattended \
  --url "${REPO_URL}" \
  --token "${RUNNER_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "${RUNNER_LABELS}" \
  --work _work \
  --replace

./svc.sh install "${RUNNER_USER}"
./svc.sh start
./svc.sh status

echo "KMJ self-hosted runner installed. Keep RUNNER_TOKEN out of shell history and logs."
