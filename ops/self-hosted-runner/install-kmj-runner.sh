#!/usr/bin/env bash
set -euo pipefail
umask 077

# Keep the one-time registration token out of commands, shell history, logs,
# and chat transcripts. Obtain it from the repository's GitHub UI.
if [[ -z "${RUNNER_TOKEN:-}" ]]; then
  if [[ ! -t 0 ]]; then
    echo "RUNNER_TOKEN is required; run interactively on the testing VM." >&2
    exit 2
  fi
  read -r -s -p "Paste the one-time GitHub registration token (hidden): " RUNNER_TOKEN
  printf '\n'
fi
[[ -n "$RUNNER_TOKEN" ]] || { echo "Empty registration token." >&2; exit 2; }
REPO_URL="${REPO_URL:-https://github.com/kmjtechno/kmj-main-platform}"
RUNNER_VERSION="${RUNNER_VERSION:-2.337.0}"
RUNNER_SHA256="${RUNNER_SHA256:-70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613}"
RUNNER_USER="${RUNNER_USER:-kmjrunner}"
RUNNER_HOME="${RUNNER_HOME:-/opt/kmj-actions-runner}"
RUNNER_NAME="${RUNNER_NAME:-kmj-main-platform-ci-$(hostname)}"
RUNNER_LABELS="${RUNNER_LABELS:-kmj-main-platform-ci}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root; the runner service itself will use ${RUNNER_USER}." >&2
  exit 1
fi

if [[ "${REPO_URL}" != "https://github.com/kmjtechno/kmj-main-platform" ]]; then
  echo "Refusing to enroll the KMJ runner with another repository." >&2
  exit 2
fi
if [[ "${RUNNER_HOME}" != "/opt/kmj-actions-runner" ]]; then
  echo "Refusing unmanaged runner installation path." >&2
  exit 2
fi
if [[ ! "${RUNNER_USER}" =~ ^[a-z_][a-z0-9_-]{0,30}$ ]]; then
  echo "Runner service account name is invalid." >&2
  exit 2
fi
if [[ ! "${RUNNER_NAME}" =~ ^[A-Za-z0-9_.-]{1,120}$ ]]; then
  echo "Runner name is invalid." >&2
  exit 2
fi
if [[ "${RUNNER_LABELS}" != "kmj-main-platform-ci" ]]; then
  echo "Runner label must match trusted CI workflow selection." >&2
  exit 2
fi
if [[ -f "${RUNNER_HOME}/.runner" || -f "${RUNNER_HOME}/.credentials" ]]; then
  echo "Existing runner registration found; refusing replacement." >&2
  exit 2
fi
if [[ -d "${RUNNER_HOME}" ]] && [[ -n "$(ls -A "${RUNNER_HOME}")" ]]; then
  echo "Runner directory is not empty; refusing an in-place overwrite." >&2
  exit 2
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
echo "${RUNNER_SHA256}  ${archive}" | sha256sum -c -
tar xzf "${archive}"
rm -f "${archive}"
chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_HOME}"

runuser -u "${RUNNER_USER}" -- ./config.sh \
  --unattended \
  --url "${REPO_URL}" \
  --token "${RUNNER_TOKEN}" \
  --name "${RUNNER_NAME}" \
  --labels "${RUNNER_LABELS}" \
  --work _work

./svc.sh install "${RUNNER_USER}"
./svc.sh start
./svc.sh status

unset RUNNER_TOKEN
echo "KMJ runner registered for the existing private repository."
echo "Cost policy: GitHub self-hosted runner usage is free; VM infrastructure costs remain yours."
echo "Confirm the runner is Online with label kmj-main-platform-ci in GitHub Settings > Actions > Runners."
echo "Keep this runner on a dedicated test VM. Never run untrusted fork code or live production workloads."
