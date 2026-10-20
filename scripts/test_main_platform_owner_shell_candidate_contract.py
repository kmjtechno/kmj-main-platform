"""Contract of the exact owner-shell immutable candidate builder; no VPS execution."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "scripts/operations/build-main-platform-candidate-20261020-owner-shell.sh").read_text()

required = (
    "ad7655615b4da4f0c87a42e4036f1de7d9dd1812",
    "platform-8070dad72c55",
    '[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]]',
    "EXPECTED_CURRENT_RELEASE_CHANGED",
    "PRODUCTION_POINTER_CHANGED",
    "SOURCE='https://github.com/kmjtechno/kmj-main-platform.git'",
    "git checkout --detach",
    "git rev-parse HEAD",
    "npm ci --ignore-scripts",
    "composer install --no-dev",
    "npm run build",
    "public/build/manifest.json",
    "vendor/autoload.php",
    "CANDIDATE_GIT_WORKTREE_DIRTY",
    "SCRATCH_SHA_MISMATCH",
    "SCRATCH_WORKTREE_DIRTY",
    "CANDIDATE_DIRTY_AFTER_ACL",
    "CANDIDATE_PUBLIC_ACL=PASS PRIVATE_ENV_NGINX=DENIED",
    'setfacl -m \'u:www-data:--x\' "$p"',
    'setfacl -R -m \'u:www-data:rX\' "$DEST/apps/platform/public"',
    'runuser -u www-data -- test -r "$DEST/apps/platform/public/index.php"',
    'runuser -u www-data -- test ! -r "$DEST/apps/platform/.env"',
    "verify_public_acl",
    "PRODUCTION_ACTIVATION=NOT_ATTEMPTED",
    "PRODUCTION_SWITCH=NOT_ATTEMPTED",
    "BACKUP_AND_APPROVAL=STILL_REQUIRED",
)
for marker in required:
    assert marker in source, f"Missing safety guard: {marker}"

for forbidden in (
    "systemctl restart",
    "systemctl reload",
    "systemctl start",
    "artisan migrate",
    "ln -sfn",
    "ln -sf",
    "ALTER ROLE",
    "chown -R",
    "git reset --hard",
    "/etc/kmj-codebridge/main-platform-production-release.json",
    "backupVerified",
    "rollbackVerified",
    "curl | bash",
    "chmod 777",
):
    assert forbidden not in source, f"Unsafe production operation: {forbidden}"

assert source.count("verify_public_acl") == 3, "Both resumed and new candidates must receive scoped ACL and env denial"
assert source.index("NGINX_PRIVATE_ENV_EXPOSED") < source.index("CANDIDATE_PUBLIC_ACL=PASS")
assert source.index("EXPECTED_CURRENT_RELEASE_CHANGED") < source.index('if [[ -e "$DEST"')
assert '[[ "$(readlink -f "$ROOT/current")" == "$before" ]]' in source
print("OWNER_SHELL_CANDIDATE_BUILDER_CONTRACT=PASS")
print("ACTUAL_CANDIDATE_BUILD=NOT_ATTEMPTED")
print("PRODUCTION_SWITCH=NOT_ATTEMPTED")
