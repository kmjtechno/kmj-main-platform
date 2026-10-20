"""No-live-write witness contract for real 98cc candidate backup and disposable DDL."""
from pathlib import Path

source=(Path(__file__).resolve().parents[1] /
    "scripts/operations/prepare-final-local-recovery-kmj-elite-20261020.sh").read_text()
required=(
    "set -Eeuo pipefail",
    "readonly TARGET_SHA=98cc5c7e1603cd2616ca2da7a8dc5f577f01c348",
    "readonly SHORT_SHA=98cc5c7e1603",
    "platform-8070dad72c55",
    "CUSTOMER_PROFILE_MIGRATION_MISSING",
    "CANDIDATE_ENV_EXPOSED",
    "PRODUCTION_DATABASE_DUMP=PASS",
    "LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS",
    "LOCAL_BACKUP_INTEGRITY PASS",
    "CUSTOMER_PROFILE_SCHEMA_ALREADY_PRESENT_REVIEW_REQUIRED",
    "CUSTOMER_PROFILE_DDL_INCOMPATIBLE",
    "CUSTOMER_PROFILE_RESTORED_SCHEMA_DDL PASS",
    "OFFLINE_CUSTOMER_DDL",
    "CREATE TABLE customer_profiles",
    "REFERENCES users(id) ON DELETE CASCADE",
    "ROLLBACK;",
    "listen_addresses=''",
    "unix_socket_directories",
    "--auth-host=reject",
    "PGPASSWORD",
    "PGCONNECT_TIMEOUT",
    "--format=custom",
    "--exit-on-error",
    "sha256sum -c",
    "os.O_WRONLY | os.O_CREAT | os.O_EXCL",
    "LOCAL_BACKUP_WITNESS PASS",
    "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED",
    "ROLLBACK_DRILL NOT_VERIFIED",
    "LARAVEL_MIGRATION_ON_PRODUCTION NOT_ATTEMPTED",
    "SMTP_INBOX_DELIVERY NOT_VERIFIED",
    "PRODUCTION_SWITCH NOT_ATTEMPTED",
    "APPROVAL_UPDATED NO",
)
for token in required:
    assert token in source, "Missing final local recovery guard: "+token
for bad in (
    "systemctl restart", "systemctl reload", "systemctl start",
    "artisan migrate", "ln -s", "ALTER ROLE", "git reset",
    "rclone copy", "scp ", "sftp ", "curl | bash",
    "backupVerified", "rollbackVerified",
    "/etc/kmj-codebridge/main-platform-production-release.json",
):
    assert bad not in source, "Unsafe production/remote side effect: "+bad
assert source.index("CUSTOMER_PROFILE_RESTORED_SCHEMA_DDL PASS") < source.index("os.O_WRONLY | os.O_CREAT | os.O_EXCL")
assert source.index("CUSTOMER_PROFILE_SCHEMA_ALREADY_PRESENT_REVIEW_REQUIRED") < source.index("OFFLINE_CUSTOMER_DDL")
assert source.count(' -h "$scratch/restore/socket"') >= 3
assert '[[ "$OLD_NAME" == platform-8070dad72c55 ]]' in source
assert '[[ ! -e "$ARCHIVE" && ! -L "$ARCHIVE" && ! -e "$WITNESS" && ! -L "$WITNESS" ]]' in source
assert '[[ "$(stat -c %U "$BACKUP_DIR")" == root ]]' in source
print("FINAL_98CC_LOCAL_RECOVERY_STATIC_CONTRACT=PASS")
print("OFFSITE_INDEPENDENT_RESTORE=NOT_VERIFIED")
print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED")
