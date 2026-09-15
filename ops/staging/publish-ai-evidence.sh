#!/usr/bin/env bash
set -euo pipefail

if [ ! -f "${KMJ_AI_PROOF_PATH:-}" ]; then
  echo 'No completed AI request in this cycle; existing evidence is unchanged.'
  exit 0
fi
test -n "${STAGING_HOST:?}"
test -n "${STAGING_USER:?}"
test -n "${STAGING_KEY:?}"
test -n "${STAGING_PATH:?}"
ssh_dir="$(mktemp -d "$RUNNER_TEMP/kmj-ai-publish.XXXXXX")"
trap 'rm -rf -- "$ssh_dir"' EXIT
printf '%s' "$STAGING_KEY" | sed 's/\\n/\n/g' | tr -d '\r' > "$ssh_dir/id_ed25519"
printf '\n' >> "$ssh_dir/id_ed25519"
chmod 600 "$ssh_dir/id_ed25519"
ssh-keygen -y -f "$ssh_dir/id_ed25519" >/dev/null
ssh-keyscan -T 10 -H "$STAGING_HOST" > "$ssh_dir/known_hosts" 2>/dev/null
payload="$(base64 -w 0 "$KMJ_AI_PROOF_PATH")"
printf -v remote_command 'bash -s -- %q %q' "$STAGING_PATH" "$payload"
ssh -i "$ssh_dir/id_ed25519" -o IdentitiesOnly=yes \
  -o UserKnownHostsFile="$ssh_dir/known_hosts" -o StrictHostKeyChecking=yes \
  -o BatchMode=yes -o ConnectTimeout=15 "$STAGING_USER@$STAGING_HOST" "$remote_command" <<'REMOTE'
set -euo pipefail
cd "$1/apps/platform"
php -r 'require "vendor/autoload.php"; $app = require "bootstrap/app.php"; $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap(); exit($app->environment("staging") ? 0 : 1);'
mkdir -p storage/app/monitoring
temporary="$(mktemp storage/app/monitoring/ai-worker.XXXXXX)"
trap 'rm -f -- "$temporary"' EXIT
printf '%s' "$2" | base64 --decode > "$temporary"
chmod 644 "$temporary"
mv "$temporary" storage/app/monitoring/ai-worker.json
echo 'Published real zero-cost completion evidence to the staging monitor.'
REMOTE
