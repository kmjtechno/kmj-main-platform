#!/usr/bin/env bash
# MAIL-00: prepare ONLY a private DKIM key and publishable public DNS value.
# No packages installed, Postfix started, external mail sent, DNS changed or Laravel edited.
set -euo pipefail
umask 077
[[ "$(id -u)" == "0" ]] || { echo "ROOT_REQUIRED"; exit 2; }
command -v openssl >/dev/null && command -v base64 >/dev/null || {
  echo "BLOCKED: openssl and coreutils required"
  exit 2
}
DOMAIN=kmjtechno.com
SELECTOR=kmj2026
KEYROOT=/etc/opendkim/keys
KEYDIR="$KEYROOT/$DOMAIN"
KEYFILE="$KEYDIR/$SELECTOR.private"
TXTFILE="$KEYDIR/$SELECTOR.txt"
for target in /etc/opendkim "$KEYROOT" "$KEYDIR" "$KEYFILE" "$TXTFILE"; do
  [[ ! -L "$target" ]] || { echo "BLOCKED: symlink in DKIM key path"; exit 2; }
done
if [[ -e "$KEYFILE" && ! -f "$KEYFILE" ]]; then
  echo "BLOCKED: existing key path is not a regular file"
  exit 2
fi
if [[ -e "$TXTFILE" && ! -f "$TXTFILE" ]]; then
  echo "BLOCKED: existing DNS key path is not a regular file"
  exit 2
fi
if [[ -d "$KEYDIR" ]]; then
  # Do not change permissions/ownership of an existing live OpenDKIM key directory.
  # Existing unrelated keys require explicit manual review.
  for existing in "$KEYDIR"/*; do
    [[ -e "$existing" ]] || continue
    [[ "$existing" == "$KEYFILE" || "$existing" == "$TXTFILE" ]] || {
      echo "BLOCKED: existing unrelated DKIM key material"
      exit 2
    }
  done
else
  install -d -o root -g root -m 0700 "$KEYDIR"
fi
if [[ ! -f "$KEYFILE" ]]; then
  temp="$(mktemp "$KEYDIR/.dkim-private.XXXXXXXX")"
  trap 'rm -f -- "${temp:-}"' EXIT
  if ! openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
    -out "$temp" >/dev/null 2>&1; then
    echo "DKIM_KEY_GENERATION=FAIL"
    exit 1
  fi
  chmod 0600 "$temp"
  mv -- "$temp" "$KEYFILE"
  temp=''
  echo "DKIM_PRIVATE_KEY=CREATED"
else
  echo "DKIM_PRIVATE_KEY=EXISTING_REUSED"
fi

# Only the public SPKI (SubjectPublicKeyInfo) is exported; never expose the private PEM.
if ! PUB="$(openssl pkey -in "$KEYFILE" -pubout -outform DER 2>/dev/null | base64 -w0)"; then
  echo "DKIM_PUBLIC_DERIVATION=FAIL"
  exit 1
fi
if [[ ! "$PUB" =~ ^[A-Za-z0-9+/=]+$ || "${#PUB}" -lt 300 ]]; then
  echo "DKIM_PUBLIC_KEY=INVALID"
  exit 1
fi
TXT="v=DKIM1; k=rsa; p=$PUB"
temp="$(mktemp "$KEYDIR/.dkim-txt.XXXXXXXX")"
trap 'rm -f -- "${temp:-}"' EXIT
printf '%s\n' "$TXT" > "$temp"
chmod 0600 "$temp"
mv -- "$temp" "$TXTFILE"
temp=''
echo "DKIM_PUBLIC_KEY_PREP=PASS"
echo "DKIM_DNS_RECORD_NAME=$SELECTOR._domainkey.$DOMAIN"
echo "DKIM_DNS_RECORD_TYPE=TXT"
echo "DKIM_DNS_RECORD_VALUE=$TXT"
echo "PUBLIC_RECORD_ONLY=SAFE_TO_COPY; PRIVATE_KEY_DO_NOT_SHARE"
echo "SMTP_ACTIVATION=NOT_ATTEMPTED"
