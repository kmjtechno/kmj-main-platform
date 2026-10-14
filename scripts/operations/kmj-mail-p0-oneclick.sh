#!/usr/bin/env bash
# KMJ MAIL-P0 one-command read-only recovery dashboard.
# Runs against a SHA-pinned GitHub revision. No arbitrary shell, SMTP send, DNS writes or Laravel env writes.
set -Eeuo pipefail
umask 077

REPO="/srv/kmj-codebridge-projects/kmj-main-platform"
APP="/home/kmjprod/current/apps/platform"
BRANCH="fix/kmj-mail-01-self-hosted-20261014"
EXPECTED_SHA="${KMJ_MAIL_PINNED_SHA:-}"
if [[ "$(id -u)" -ne 0 ]]; then echo "ROOT_REQUIRED"; exit 2; fi
if [[ ! "$EXPECTED_SHA" =~ ^[a-f0-9]{40}$ ]]; then
  echo "PINNED_SHA_REQUIRED: pass KMJ_MAIL_PINNED_SHA=<reviewed SHA>"; exit 2
fi
[[ -d "$REPO/.git" ]] || { echo "CODEBRIDGE_REPO=BLOCKED_NOT_FOUND"; exit 2; }
OWNER="$(stat -c %U "$REPO")"
if [[ -z "$OWNER" || "$OWNER" == "root" ]]; then
  echo "CODEBRIDGE_REPO=BLOCKED_UNEXPECTED_OWNER"; exit 2
fi
echo "=== 1. CODEBRIDGE PINNED SOURCE ==="
runuser -u "$OWNER" -- git -C "$REPO" fetch --no-tags origin "refs/heads/$BRANCH"
ACTUAL="$(runuser -u "$OWNER" -- git -C "$REPO" rev-parse FETCH_HEAD)"
[[ "$ACTUAL" == "$EXPECTED_SHA" ]] || {
  echo "CODEBRIDGE_SOURCE=FAIL_SHA_MISMATCH"
  exit 2
}
echo "CODEBRIDGE_SOURCE=PASS_PINNED_SHA"
TMP="$(mktemp -d -t kmj-mail-p0.XXXXXXXX)"
trap 'rm -rf -- "$TMP"' EXIT
for filename in kmj-mail-00-readiness.sh kmj-mail-00-verify-dkim-dns.sh; do
  runuser -u "$OWNER" -- git -C "$REPO" show "$EXPECTED_SHA:scripts/operations/$filename" > "$TMP/$filename"
  bash -n "$TMP/$filename"
done
echo "MAIL_SCRIPTS_BASH_SYNTAX=PASS"
runuser -u "$OWNER" -- git -C "$REPO" show \
  "$EXPECTED_SHA:scripts/operations/kmj-mail-cloudflare-dkim.py" > "$TMP/kmj-mail-cloudflare-dkim.py"
if python3 - "$TMP/kmj-mail-cloudflare-dkim.py" <<'PY'
import sys
from pathlib import Path
compile(Path(sys.argv[1]).read_text(), sys.argv[1], 'exec')
PY
then
  echo "CLOUDFLARE_DKIM_PUBLISHER_SYNTAX=PASS"
else
  echo "CLOUDFLARE_DKIM_PUBLISHER_SYNTAX=FAIL"
  exit 2
fi

# Optional one-click, idempotent public-key-only DNS creation.
# Authorized secrets stay inside a root-owned file, not environment, logs or chat.
if [[ -f /etc/kmj-mail/cloudflare-dns.token && "${KMJ_MAIL_DNS_WRITE_APPROVED:-no}" == "yes" ]]; then
  python3 "$TMP/kmj-mail-cloudflare-dkim.py" --apply || \
    echo "CLOUDFLARE_PUBLIC_DKIM=BLOCKED_NEEDS_REVIEW"
else
  echo "CLOUDFLARE_PUBLIC_DKIM=NO_SCOPED_TOKEN_OR_WRITE_APPROVAL"
fi

echo "=== 2. EFFECTIVE LARAVEL RUNTIME ==="
if [[ -f "$APP/artisan" && -f "$APP/vendor/autoload.php" ]]; then
  APP_OWNER="$(stat -c %U "$APP/artisan")"
  if [[ "$APP_OWNER" == "root" ]]; then APP_OWNER=kmjprod; fi
  if ! getent passwd "$APP_OWNER" >/dev/null; then
    echo "LARAVEL_RUNTIME=BLOCKED_UNEXPECTED_APP_OWNER"
  else
    (
      cd "$APP"
      runuser -u "$APP_OWNER" -- php artisan tinker --execute='
      echo "MAILER=".config("mail.default").PHP_EOL;
      echo "QUEUE=".config("queue.default").PHP_EOL;
      echo "MAIL_FROM_CONFIGURED=".(filter_var(config("mail.from.address"), FILTER_VALIDATE_EMAIL) ? "yes" : "no").PHP_EOL;
      '
    ) 2>&1 | grep -E '^(MAILER|QUEUE|MAIL_FROM_CONFIGURED)=' || \
      echo "LARAVEL_RUNTIME=BLOCKED_NO_SAFE_OUTPUT"
  fi
else
  echo "PRODUCTION_APP=BLOCKED_NOT_FOUND"
fi
systemctl is-active kmj-main-platform-queue.service 2>/dev/null |
  sed 's/^/PRODUCTION_QUEUE_WORKER=/' || true
systemctl is-active postfix 2>/dev/null | sed 's/^/POSTFIX=/' || true
systemctl is-active opendkim 2>/dev/null | sed 's/^/OPENDKIM=/' || true

echo "=== 3. SENDER DNS + NETWORK ==="
if command -v curl >/dev/null; then
  HTTP_EGRESS_IP="$(curl -4fsS --max-time 8 https://api.ipify.org || true)"
else
  HTTP_EGRESS_IP=""
fi
if [[ "$HTTP_EGRESS_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "PUBLIC_HTTP_EGRESS_IPV4=$HTTP_EGRESS_IP"
else
  echo "PUBLIC_HTTP_EGRESS_IPV4=UNVERIFIED"
fi
echo "SMTP_EGRESS_IPV4=NOT_ATTESTED_BY_PROVIDER"
if command -v dig >/dev/null; then
  [[ -z "$HTTP_EGRESS_IP" ]] || {
    printf 'MAIL_HOST_A='
    dig +time=3 +tries=1 +short A mail.kmjtechno.com | paste -sd ',' -
    printf 'PUBLIC_HTTP_IP_PTR='
    dig +time=3 +tries=1 +short -x "$HTTP_EGRESS_IP" | paste -sd ',' -
  }
  echo "SPF_RECORDS_COUNT=$(dig +time=3 +tries=1 +short TXT kmjtechno.com | grep -ci '^"v=spf1 ' || true)"
  echo "DMARC_PRESENT=$(dig +time=3 +tries=1 +short TXT _dmarc.kmjtechno.com | grep -ci 'v=DMARC1' || true)"
  echo "DKIM_SELECTOR_TXT_PRESENT=$(dig +time=3 +tries=1 +short TXT kmj2026._domainkey.kmjtechno.com | grep -ci 'v=DKIM1' || true)"
  if [[ -f /etc/opendkim/keys/kmjtechno.com/kmj2026.private ]]; then
    if bash "$TMP/kmj-mail-00-verify-dkim-dns.sh"; then
      echo "DKIM_MATCHING=PASS"
    else
      echo "DKIM_MATCHING=BLOCKED"
    fi
  else
    echo "DKIM_PRIVATE_KEY=BLOCKED_MISSING"
  fi
else
  echo "DNS_TOOLS=BLOCKED_MISSING_DIG"
fi
echo "=== 4. EXACT-HEAD ISOLATED QA (NON-ROOT) ==="
if [[ "${KMJ_MAIL_RUN_EXACT_HEAD_QA:-yes}" == "yes" ]]; then
  if [[ -f "$REPO/apps/platform/vendor/autoload.php" && -x "$REPO/apps/platform/node_modules/.bin/vp" ]]; then
    QA_DIR="$(mktemp -d -t kmj-mail-oneclick-qa.XXXXXXXX)"
    chown "$OWNER" "$QA_DIR"
    runuser -u "$OWNER" -- git -C "$REPO" show \
      "$EXPECTED_SHA:scripts/ci/verify-registration-mail-pr.sh" > "$QA_DIR/verify.sh"
    chmod 0644 "$QA_DIR/verify.sh"
    if runuser -u "$OWNER" -- bash -c 'cd "$1" && bash "$2" "$3"' \
      _ "$REPO" "$QA_DIR/verify.sh" "$EXPECTED_SHA" > "$QA_DIR/qa.log" 2>&1; then
      echo "MAIL_PR_EXACT_SHA_QA=PASS"
    else
      echo "MAIL_PR_EXACT_SHA_QA=FAIL_OR_BLOCKED"
    fi
    grep -E '^(PASS:|FAIL:|MAIL_QA_|BLOCKED:)' "$QA_DIR/qa.log" | tail -35 || true
    rm -rf -- "$QA_DIR"
  else
    echo "MAIL_PR_EXACT_SHA_QA=BLOCKED_DEPENDENCIES_ABSENT"
  fi
else
  echo "MAIL_PR_EXACT_SHA_QA=SKIPPED_BY_OPERATOR"
fi

echo "=== 5. HOST POLICY + ACTIVATION GATES ==="
echo "PROVIDER_SMTP_PERMISSION=NOT_VERIFIED_BY_SCRIPT"
echo "PTR_CHANGE_PERMISSION=NOT_VERIFIED_BY_SCRIPT"
echo "PR423_GITHUB_HOSTED_CI=MUST_VERIFY_SEPARATELY_FROM_LOCAL_QA"
echo "AUTHENTICATED_INBOX_DELIVERY=NOT_VERIFIED"
echo "CUSTOMER_SIGNED_VERIFICATION=NOT_VERIFIED"
echo "NO_DNS_OR_MAIL_CONFIGURATION_WAS_MODIFIED=PASS"
echo "NEXT=Publish DKIM DNS via authorized Cloudflare account; request SMTP policy and PTR from hosting provider; only then stage and test MAIL-01."
