from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/"scripts/operations/build-main-platform-candidate-kmj-elite.sh").read_text()
required=[
  "8070dad72c551e5e13d1a78b0d4e6933c2d2ae9b",
  '[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]]',
  "readlink -f",
  "runuser -u kmjprod",
  "git checkout --detach",
  "git rev-parse HEAD",
  "composer install --no-dev",
  "npm ci --ignore-scripts",
  "npm run build",
  "public/build/manifest.json",
  "vendor/autoload.php",
  "PRODUCTION_ACTIVATION=NOT_ATTEMPTED",
  "PRODUCTION_SWITCH=NOT_ATTEMPTED",
  "BACKUP_AND_APPROVAL=STILL_REQUIRED",
]
for p in required:
  assert p in source, f"candidate builder missing required protection: {p}"
for forbidden in (
  "systemctl restart", "systemctl reload", "artisan migrate",
  "ln -sfn", "ln -sf", "ALTER ROLE", "chown -R", "git reset --hard",
  "/etc/kmj-codebridge/main-platform-production-release.json",
  "pre-deploy-8070dad72c55.json",
):
  assert forbidden not in source, f"unsafe production action: {forbidden}"
print("Candidate build non-deployment contract PASS")
