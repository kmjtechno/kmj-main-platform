"""Static safety fence for SHA-pinned production candidate; NEVER deploy in CI."""
from pathlib import Path

script=(Path(__file__).resolve().parents[1] /
    "scripts/operations/build-main-platform-candidate-20261020-final.sh").read_text()
required=(
    "98cc5c7e1603cd2616ca2da7a8dc5f577f01c348",
    "platform-8070dad72c55",
    "EXPECTED_CURRENT_RELEASE_CHANGED",
    "PRODUCTION_POINTER_CHANGED",
    "git checkout --detach",
    "SCRATCH_SHA_MISMATCH",
    "CANDIDATE_FINAL_SHA_MISMATCH",
    "CANDIDATE_GIT_WORKTREE_DIRTY",
    "npm ci --ignore-scripts",
    "composer install --no-dev",
    "npm run build",
    "public/build/manifest.json",
    "apps/platform/database/migrations/2026_10_20_070000_create_customer_profiles_table.php",
    "CANDIDATE_PUBLIC_ACL=PASS PRIVATE_ENV_NGINX=DENIED",
    'setfacl -m \'u:www-data:--x\' "$p"',
    'setfacl -R -m \'u:www-data:rX\' "$DEST/apps/platform/public"',
    'runuser -u www-data -- test ! -r "$DEST/apps/platform/.env"',
    "CUSTOMER_PROFILE_MIGRATION=NOT_ATTEMPTED",
    "OFFSITE_INDEPENDENT_RESTORE=NOT_VERIFIED",
    "SMTP_DELIVERY=NOT_VERIFIED",
    "BACKUP_AND_APPROVAL=STILL_REQUIRED",
    "PRODUCTION_SWITCH=NOT_ATTEMPTED",
)
for token in required:
    assert token in script, "Missing source-bound candidate guard: "+token
assert script.count("verify_public_acl") == 3
assert script.index("EXPECTED_CURRENT_RELEASE_CHANGED") < script.index('if [[ -e "$DEST"')
assert script.index("NGINX_PRIVATE_ENV_EXPOSED") < script.index("CANDIDATE_PUBLIC_ACL=PASS")
assert '[[ "$(readlink -f "$ROOT/current")" == "$before" ]]' in script
for bad in (
    "systemctl restart", "systemctl reload", "systemctl start",
    "artisan migrate", "ln -sfn", "ln -sf", "ALTER ROLE",
    "chown -R", "git reset --hard", "/etc/kmj-codebridge/main-platform-production-release.json",
    "backupVerified", "rollbackVerified", "curl | bash", "chmod 777",
):
    assert bad not in script, "Unsafe candidate side effect: "+bad
print("FINAL_98CC_CANDIDATE_STATIC_CONTRACT=PASS")
print("ACTUAL_PRODUCTION_BUILD=NOT_ATTEMPTED")
print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
