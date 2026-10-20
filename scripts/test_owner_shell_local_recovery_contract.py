"""Owner-shell rollback/local backup script static contract: never deploy or infer offsite success."""
from pathlib import Path

source=(Path(__file__).resolve().parents[1]/"scripts/operations/prepare-owner-shell-local-recovery-kmj-elite-20261020.sh").read_text()
must=[
 "set -Eeuo pipefail",
 '$(hostname -s)" == KMJ-elite',
 "ad7655615b4da4f0c87a42e4036f1de7d9dd1812",
 "readonly SHORT_SHA=ad7655615b4d",
 "platform-8070dad72c55",
 "CANDIDATE_PUBLIC_UNREADABLE",
 "CANDIDATE_ENV_EXPOSED",
 "PRODUCTION_DATABASE_DUMP=PASS",
 "LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS",
 "LOCAL_SCHEMA_VERIFICATION PASS",
 "listen_addresses=''",
 "--auth-host=reject",
 "PGPASSWORD",
 "PGCONNECT_TIMEOUT",
 "--format=custom",
 "--exit-on-error",
 "sha256sum -c",
 "O_NOFOLLOW",
 "O_EXCL",
 "chown root:kmjprod",
 "install -d -o kmjprod -g kmjprod",
 "restore/socket",
 "restore/database.dump",
 "pre-deploy-$SHORT_SHA.tar.gz",
 "currentRelease",
 "backupSha256",
 "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED",
 "ROLLBACK_DRILL NOT_VERIFIED",
 "PRODUCTION_SWITCH NOT_ATTEMPTED",
 "APPROVAL_UPDATED NO",
]
for marker in must:
    assert marker in source, f"Missing recovery guard: {marker}"
for bad in [
 "systemctl restart", "systemctl reload", "systemctl start", "artisan migrate",
 "ln -s", "rm -rf /home", "git reset", "ALTER ROLE",
 "backupVerified", "rollbackVerified",
 "/etc/kmj-codebridge/main-platform-production-release.json",
 "rclone copy", "curl | bash",
]:
    assert bad not in source, f"Unsafe live or offsite side-effect: {bad}"
assert source.index("LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS") < source.index("os.O_WRONLY | os.O_CREAT | os.O_EXCL"), "Witness publication before successful restore"
assert '[[ "$OLD_NAME" == platform-8070dad72c55 ]]' in source
assert '[[ ! -e "$ARCHIVE" && ! -L "$ARCHIVE" && ! -e "$WITNESS" && ! -L "$WITNESS" ]]' in source
assert '[[ "$(stat -c %U "$BACKUP_DIR")" == root ]]' in source
assert source.count("runuser -u www-data -- test") == 2
print("OWNER_SHELL_LOCAL_RECOVERY_STATIC_CONTRACT=PASS")
print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
