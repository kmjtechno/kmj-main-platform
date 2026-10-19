#!/usr/bin/env bash
# KMJ TECHNO: zero-cost mail recovery visibility only.
# NEVER sends email, changes DNS, reads secrets, restarts services,
# changes mail transports, alters the database or enables registration.
set -Eeuo pipefail
umask 077

APP_ROOT="$(printenv KMJ_MAIL_APP_ROOT 2>/dev/null || :)"
if [[ -z "$APP_ROOT" ]]; then
    APP_ROOT="/home/kmjprod/current/apps/platform"
fi
readonly APP_ROOT
readonly PUBLIC_IP="103.212.136.154"
readonly MAIL_HOSTNAME="mail.kmjtechno.com"

status() {
    printf '%s=%s\n' "$1" "$2"
}

loopback_tcp() {
    local port="$1"
    if command -v timeout >/dev/null 2>&1 &&
        timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/$1' _ "$port" >/dev/null 2>&1; then
        printf 'LISTENING'
    else
        printf 'UNAVAILABLE'
    fi
}

status MODE READ_ONLY
status MUTATIONS NONE
status SECRETS_PRINTED NO
status PRODUCTION_MAIL_SENT NO
status CUSTOMER_DATA_READ NO

if command -v getent >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    if timeout 6 getent ahostsv4 "$MAIL_HOSTNAME" 2>/dev/null |
        awk '{print $1}' | grep -Fxq "$PUBLIC_IP"; then
        status MAIL_FORWARD_A MATCH
    else
        status MAIL_FORWARD_A NOT_VERIFIED
    fi
    if timeout 6 getent hosts "$PUBLIC_IP" 2>/dev/null |
        awk '{print tolower($0)}' | grep -Eq '(^|[[:space:]])mail[.]kmjtechno[.]com[.]?([[:space:]]|$)'; then
        status VPS_PTR_RDNS MATCH
    else
        status VPS_PTR_RDNS NOT_VERIFIED
    fi
else
    status DNS_CHECKS UNAVAILABLE
fi

if command -v docker >/dev/null 2>&1; then
    status DOCKER_CLI PRESENT
else
    status DOCKER_CLI MISSING
fi
if command -v posta >/dev/null 2>&1; then
    status POSTA_BINARY_IN_PATH PRESENT
else
    status POSTA_BINARY_IN_PATH NOT_FOUND
fi

# Socket visibility is not SMTP acceptance or inbox delivery.
status POSTA_API_LOOPBACK_9000 "$(loopback_tcp 9000)"
status POSTA_RELAY_LOOPBACK_2526 "$(loopback_tcp 2526)"

if command -v pgrep >/dev/null 2>&1 &&
    pgrep -f '(^|/)posta[[:space:]]+worker' >/dev/null 2>&1; then
    status POSTA_WORKER_PROCESS SEEN
else
    status POSTA_WORKER_PROCESS NOT_VERIFIED
fi

if [[ -f "$APP_ROOT/artisan" ]] && command -v php >/dev/null 2>&1 &&
    command -v timeout >/dev/null 2>&1; then
    # Doctor emits secret-free JSON. Never print its raw output.
    doctor="$(
        cd "$APP_ROOT"
        timeout 15 php artisan kmj:mail:doctor --json 2>/dev/null
    )" || doctor=""
    if [[ "$doctor" == *'"can_attempt_external_delivery":true'* ]]; then
        status LARAVEL_MAIL_CONFIG CONFIGURED_ATTEMPT_ONLY
    elif [[ "$doctor" == *'"can_attempt_external_delivery":false'* ]]; then
        status LARAVEL_MAIL_CONFIG BLOCKED
    else
        status LARAVEL_MAIL_CONFIG DOCTOR_NOT_AVAILABLE
    fi
else
    status LARAVEL_MAIL_CONFIG APP_OR_PHP_UNAVAILABLE
fi

# Never claim success from a local listener or a queued message.
status VERIFIED_EXTERNAL_RECIPIENT_DELIVERY UNVERIFIED
status SIGNED_EMAIL_VERIFICATION_LINK_TEST UNVERIFIED
status SAFE_TO_ENABLE_CUSTOMER_SIGNUP NOT_PROVEN
status DIAGNOSTIC_COMPLETED YES
