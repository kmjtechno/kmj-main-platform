from pathlib import Path
source=(Path(__file__).resolve().parents[1]/"scripts/operations/prepare-main-platform-local-recovery-kmj-elite.sh").read_text()
must=[
 "set -Eeuo pipefail",
 '$(hostname -s)" == KMJ-elite',
 "8070dad72c551e5e13d1a78b0d4e6933c2d2ae9b",
 "platform-54142f844c0b",
 "PRODUCTION_DATABASE_DUMP=PASS",
 "LOCAL_DISPOSABLE_POSTGRES_RESTORE",
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
 "currentRelease",
 "backupSha256",
 "OFFSITE_INDEPENDENT_RESTORE NOT_VERIFIED",
 "ROLLBACK_DRILL NOT_VERIFIED",
 "PRODUCTION_SWITCH NOT_ATTEMPTED",
 "APPROVAL_UPDATED NO",
]
for token in must:
    assert token in source, f"Recovery safety contract missing: {token}"
for forbidden in [
 "systemctl restart", "systemctl reload", "artisan migrate",
 "ln -s", "rm -rf /home", "git reset",
 "backupVerified", "rollbackVerified",
 "/etc/kmj-codebridge/main-platform-production-release.json",
 "rclone copy", "curl | bash",
]:
    assert forbidden not in source, f"Unexpected production/offsite mutation: {forbidden}"
assert source.index("LOCAL_DISPOSABLE_POSTGRES_RESTORE PASS") < source.index("os.O_WRONLY | os.O_CREAT | os.O_EXCL"), "witness must only publish after independent disposable restore"
print("Local recovery backup contract PASS")
