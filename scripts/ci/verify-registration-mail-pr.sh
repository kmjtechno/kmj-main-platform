#!/usr/bin/env bash
# Isolated exact-head regression verification for KMJ account onboarding.
# No live SMTP traffic, user mail, deployment or production database access.
set -Eeuo pipefail
umask 077

[[ ${1:-} =~ ^[0-9a-f]{40}$ ]] || { echo 'Usage: verify-registration-mail-pr.sh <exact-SHA>' >&2; exit 2; }
sha="$1"
[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: run as non-root repo owner' >&2; exit 2; }
repo="$(git rev-parse --show-toplevel)"
[[ "$(basename "$repo")" == 'kmj-main-platform' ]] || { echo 'BLOCKED: incorrect repo' >&2; exit 2; }
git -C "$repo" cat-file -e "${sha}^{commit}" || { echo 'BLOCKED: fetch PR head first' >&2; exit 3; }

src="$repo/apps/platform"
if [[ -L "$src/vendor" || -L "$src/node_modules" ]]; then
  echo 'BLOCKED: linked top-level QA dependencies could mutate production paths' >&2
  exit 3
fi
[[ -f "$src/vendor/autoload.php" ]] || { echo 'BLOCKED: PHP vendor dependencies absent' >&2; exit 3; }
[[ -d "$src/node_modules" && -x "$src/node_modules/.bin/vp" ]] || {
  echo 'BLOCKED: Node and Vite+ dependencies absent' >&2; exit 3;
}
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-mail-qa.XXXXXXXX")"
cleanup() {
  git -C "$repo" worktree remove --force "$tmp/tree" >/dev/null 2>&1 || true
  rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM
git -C "$repo" worktree add --detach "$tmp/tree" "$sha" >/dev/null
[[ "$(git -C "$tmp/tree" rev-parse HEAD)" == "$sha" ]] || exit 3
cp -a "$src/vendor" "$tmp/tree/apps/platform/vendor"
cp -a "$src/node_modules" "$tmp/tree/apps/platform/node_modules"
cd "$tmp/tree/apps/platform"
printf '# disposable QA, no live SMTP passwords\n' > .env
chmod 600 .env
export APP_ENV=testing APP_DEBUG=false APP_URL=http://localhost
export APP_KEY="base64:$(php -r 'echo base64_encode(random_bytes(32));')"
export MAIL_MAILER=array DB_CONNECTION=sqlite DB_DATABASE=':memory:'
export CACHE_STORE=array SESSION_DRIVER=array QUEUE_CONNECTION=sync

failed=0
echo '== MAIL-00/01 shell syntax =='
if bash -n "$tmp/tree/scripts/operations/kmj-mail-00-readiness.sh" \
  && bash -n "$tmp/tree/scripts/operations/kmj-mail-00-prepare-dkim.sh" \
  && bash -n "$tmp/tree/scripts/operations/kmj-mail-00-verify-dkim-dns.sh" \
  && bash -n "$tmp/tree/scripts/operations/kmj-mail-p0-oneclick.sh" \
  && bash -n "$tmp/tree/scripts/operations/kmj-mail-01-bootstrap.sh"; then
  echo 'PASS: mail install/preflight Bash parser'
else
  echo 'FAIL: mail script shell syntax'; failed=$((failed+1))
fi
echo '== Python mail-DNS code compilation =='
if python3 -m py_compile "$tmp/tree/scripts/operations/kmj-mail-cloudflare-dkim.py" \
    "$tmp/tree/scripts/operations/test-kmj-mail-cloudflare-dkim.py"; then
  echo 'PASS: Cloudflare DNS publisher/test Python syntax'
else
  echo 'FAIL: Cloudflare DNS publisher Python syntax'; failed=$((failed+1))
fi
echo '== Offline Cloudflare DKIM DNS publishing regression tests =='
if python3 "$tmp/tree/scripts/operations/test-kmj-mail-cloudflare-dkim.py"; then
  echo 'PASS: DKIM publish idempotency and no-write guards'
else
  echo 'FAIL: Cloudflare DKIM publisher offline regression tests'; failed=$((failed+1))
fi
echo "MAIL_QA_SHA=$sha"
echo '== Production Vite/Wayfinder build before Inertia HTTP tests =='
if npm run build && test -s public/build/manifest.json; then
  echo 'PASS: Vite build, generated manifest'
else
  echo 'FAIL: Vite build'; failed=$((failed+1))
fi
echo '== PHP syntax and Laravel mail readiness/registration tests =='
if php -l app/Services/Mail/RegistrationMailReadiness.php \
  && php -l app/Console/Commands/RegistrationMailDoctorCommand.php \
  && php -l app/Actions/Fortify/CreateNewUser.php \
  && php -l app/Models/User.php \
  && php -l tests/Feature/Auth/RegistrationTest.php \
  && php -l tests/Feature/Auth/VerificationNotificationTest.php \
  && php artisan test --filter='RegistrationMailReadinessTest|EmailVerificationTest|VerificationNotificationTest|RegistrationTest' --display-warnings --fail-on-warning --no-ansi; then
  echo 'PASS: PHP syntax and onboarding regression tests'
else
  echo 'FAIL: PHP syntax or onboarding regression tests'; failed=$((failed+1))
fi
echo '== PHP formatting and static analysis =='
if ./vendor/bin/pint --test app/Services/Mail/RegistrationMailReadiness.php app/Console/Commands/RegistrationMailDoctorCommand.php app/Actions/Fortify/CreateNewUser.php app/Providers/FortifyServiceProvider.php app/Models/User.php tests/Unit/RegistrationMailReadinessTest.php tests/Feature/Auth/EmailVerificationTest.php tests/Feature/Auth/RegistrationTest.php tests/Feature/Auth/VerificationNotificationTest.php; then
  echo 'PASS: Pint'
else
  echo 'FAIL: Pint'; failed=$((failed+1))
fi
if ./vendor/bin/phpstan analyse --no-progress; then echo 'PASS: PHPStan'
else echo 'FAIL: PHPStan'; failed=$((failed+1)); fi
echo '== Frontend QA and build =='
if npm run types:check; then echo 'PASS: TypeScript'
else echo 'FAIL: TypeScript'; failed=$((failed+1)); fi
if npm run check; then echo 'PASS: frontend lint and Node contracts'
else echo 'FAIL: frontend lint or Node contracts'; failed=$((failed+1)); fi
echo "MAIL_QA_FAILURES=$failed SHA=$sha"
(( failed == 0 )) || exit 1
echo 'PASS: isolated source gate; real SMTP/inbox delivery NOT verified'
