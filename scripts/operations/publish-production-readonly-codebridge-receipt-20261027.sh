#!/usr/bin/env bash
# Operator-triggered read-only production release diagnostics -> CodeBridge receipt.
# Executes TWO exact source-pinned audit scripts only; NOT arbitrary shell or deploy.
set -Eeuo pipefail
umask 077
export LC_ALL=C
block() { printf 'KMJ_PROD_RECEIPT=BLOCKED_%s\n' "$1"; exit 2; }
[[ "$(hostname -s)" == KMJ-elite && "$(id -u)" == 0 ]] || block HOST
[[ "$#" == 0 ]] || block NO_ARGUMENTS_ALLOWED

root=/srv/kmj-codebridge-projects/kmj-main-platform/work/qa
latest="$root/KMJ_PRODUCTION_RELEASE_RECEIPT_LATEST_20261027.json"
source=https://raw.githubusercontent.com/kmjtechno/kmj-main-platform
target=06caf93699c0e791df22c6679aac87a1c14c6332
expected_current=platform-8070dad72c55
[[ -d "$root" && ! -L "$root" ]] || block CODEBRIDGE_WORKSPACE_NOT_READY
[[ -L /home/kmjprod/current ]] || block PROD_LINK_MISSING
[[ "$(readlink -f /home/kmjprod/current)" == "/home/kmjprod/releases/$expected_current" ]] || block PROD_BASELINE_DRIFT
for binary in curl git python3 mktemp timeout sha256sum; do
  command -v "$binary" >/dev/null 2>&1 || block "MISSING_$binary"
done

# A moving branch or new release invalidates this fixed evidence contract.
main="$(git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/main | awk '{print $1}')" || block MAIN_UNREACHABLE
approved="$(git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/staging-approved | awk '{print $1}')" || block APPROVED_UNREACHABLE
[[ "$main" == "$target" && "$approved" == "$target" ]] || block SHA_DRIFT

scratch="$(mktemp -d /root/.kmj-codebridge-owner-receipt.XXXXXXXX)" || block SCRATCH
trap 'rm -rf -- "$scratch"' EXIT

fetch() {
  local commit="$1" path="$2" blob="$3" dest="$4"
  curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
    --connect-timeout 8 --max-time 30 "$source/$commit/$path" -o "$dest" || block DOWNLOAD
  [[ "$(git hash-object "$dest")" == "$blob" ]] || block PINNED_GIT_BLOB
}
fetch 11837b1d25e597a5a2f90622c18607edc765078e \
  scripts/operations/audit-production-approval-blockers-20261027.py \
  2967eb9875ed3b9d76a75a0949864707b72056eb \
  "$scratch/approval.py"
fetch 4c54826bfd31689768eab00d8240fa8e2c2aba01 \
  scripts/operations/audit-production-candidate-storage-20261027.py \
  888c670a26523a083a3096306b745043148dc5df \
  "$scratch/storage.py"
echo "KMJ_PROD_RECEIPT_PINNED_SCRIPTS=PASS"

started="$(date -u +%FT%TZ)"
set +e
timeout --signal=TERM --kill-after=5s 90s python3 -B "$scratch/approval.py" >"$scratch/approval.log" 2>&1
approval_code=$?
timeout --signal=TERM --kill-after=5s 90s python3 -B "$scratch/storage.py" "$target" >"$scratch/storage.log" 2>&1
storage_code=$?
set -e
ended="$(date -u +%FT%TZ)"
if [[ "$(readlink -f /home/kmjprod/current)" != "/home/kmjprod/releases/$expected_current" ]]; then
  block PROD_CHANGED_DURING_AUDIT
fi

# Redact to allowlisted keys and strict values. Raw audit logs remain root-private
# and are deleted on exit. This file is convenience evidence, not release approval.
python3 - "$scratch/approval.log" "$scratch/storage.log" \
  "$scratch/receipt.json" "$approval_code" "$storage_code" "$started" "$ended" <<'PY'
import hashlib, json, pathlib, re, sys
a, b, out, ac, sc, start, end = sys.argv[1:]
keys = {
    "PROD_GATE_CURRENT_RELEASE", "PROD_GATE_CURRENT_SOURCE_GIT",
    "PROD_GATE_CURRENT_SOURCE_SHA", "PROD_GATE_PROTECTED_APPROVAL",
    "PROD_GATE_MANIFEST_TARGET_SHA", "PROD_GATE_MANIFEST_EXPECTED_RELEASE",
    "PROD_GATE_MANIFEST_EXPECTED_CURRENT", "PROD_GATE_MANIFEST_TARGET_ALREADY_CURRENT",
    "PROD_GATE_REMOTE_MAIN_SHA", "PROD_GATE_PROMOTION_REF",
    "PROD_GATE_CURRENT_MAIN_CANDIDATE", "PROD_GATE_CANDIDATE_RUNTIME_ENV",
    "PROD_GATE_TARGET_BACKUP_WITNESS", "PROD_GATE_TARGET_BACKUP_ARCHIVE",
    "PROD_GATE_DISPOSABLE_RESTORE_EVIDENCE", "PROD_GATE_CANDIDATE_OWNER_AUTH_QA",
    "PROD_GATE_STORAGE_CONTINUITY", "PROD_GATE_RESULT",
    "PROD_GATE_NGINX", "PROD_GATE_PHP_FPM", "PROD_GATE_RELEASE_UNIT",
    "PROD_GATE_APPROVAL_RENEWAL", "PROD_GATE_RELEASE_CUTOVER",
    "PROD_GATE_DATABASE_CHANGES", "LIVE_RELEASE", "CANDIDATE_SHA",
    "PUBLIC_OLD_FILES", "PUBLIC_CANDIDATE_FILES", "PUBLIC_MATCHING_FILES",
    "PUBLIC_CONFLICTS", "PUBLIC_OLD_ONLY", "PUBLIC_CANDIDATE_ONLY",
    "PUBLIC_OLD_SYMLINKS", "PUBLIC_CANDIDATE_SYMLINKS",
    "PUBLIC_CONTINUITY", "PRIVATE_OLD_FILES", "PRIVATE_CANDIDATE_FILES",
    "PRIVATE_MATCHING_FILES", "PRIVATE_CONFLICTS", "PRIVATE_OLD_ONLY",
    "PRIVATE_CANDIDATE_ONLY", "PRIVATE_OLD_SYMLINKS",
    "PRIVATE_CANDIDATE_SYMLINKS", "PRIVATE_CONTINUITY",
    "KMJ_PROD_STORAGE_AUDIT", "PRODUCTION_POINTER"
}
facts = {}
raw_hashes = {}
for source in (a, b):
    data = pathlib.Path(source).read_bytes()
    if len(data) > 128000:
        raise SystemExit("RECEIPT_LOG_TOO_LARGE")
    raw_hashes["approval" if source == a else "storage"] = hashlib.sha256(data).hexdigest()
    for line in data.decode("utf-8", "replace").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in keys and re.fullmatch(r"[A-Za-z0-9._:/-]{1,128}", value):
            facts[key] = value
status = (
    "READ_ONLY_COMPLETE"
    if int(ac) == int(sc) == 0
       and facts.get("PROD_GATE_RESULT") == "READ_ONLY_COMPLETE"
       and facts.get("KMJ_PROD_STORAGE_AUDIT") == "READ_ONLY_COMPLETE"
       and facts.get("PRODUCTION_POINTER") == "UNCHANGED"
    else "FAILED_OR_INCOMPLETE"
)
receipt = {
  "schema": "kmj-codebridge-production-owner-receipt-v1",
  "host": "KMJ-elite", "project": "kmj-main-platform",
  "profile": "fixed-pinned-production-approval-and-storage-audits",
  "started_utc": start, "ended_utc": end,
  "audit_exit_codes": {"approval": int(ac), "storage": int(sc)},
  "status": status, "facts": facts, "raw_log_sha256": raw_hashes,
  "limits": "Read-only operator-run observation; not proof of authenticated QA, rollback or independent offsite restore; cannot authorize protected activation."
}
pathlib.Path(out).write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
PY

# Keep the receipt CodeBridge-readable and non-secret; refuse symlink destinations.
[[ ! -L "$latest" ]] || block RECEIPT_SYMLINK
if [[ -e "$latest" ]]; then
  [[ -f "$latest" && "$(stat -c %u "$latest")" == 0 ]] || block RECEIPT_DEST_UNSAFE
fi
install -o root -g root -m 0644 "$scratch/receipt.json" "$scratch/staged.json"
mv -T "$scratch/staged.json" "$latest"
echo "KMJ_PROD_RECEIPT=WRITTEN_CODEBRIDGE_READABLE"
echo "KMJ_PROD_RECEIPT_PATH=$latest"
echo "KMJ_PROD_RECEIPT_APPROVAL_EXIT=$approval_code"
echo "KMJ_PROD_RECEIPT_STORAGE_EXIT=$storage_code"
exit $(( approval_code != 0 || storage_code != 0 ))
