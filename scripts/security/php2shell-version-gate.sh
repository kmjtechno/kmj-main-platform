#!/usr/bin/env bash
# Read-only, fail-closed PHP2Shell runtime version gate.
# CVE-2026-109618 / CVE-2026-109619 (PHP security releases 2026-10-21).
set -euo pipefail
command -v php >/dev/null || { echo "PHP_CLI=MISSING"; exit 2; }
php -r '
$minimum = ["8.2" => 35, "8.3" => 36, "8.4" => 27, "8.5" => 12];
$series = PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;
$patch = PHP_RELEASE_VERSION;
if (!array_key_exists($series, $minimum)) {
    fwrite(STDERR, "PHP_SECURITY_GATE=FAIL_UNSUPPORTED_SERIES series=".$series."\n");
    exit(2);
}
if ($patch < $minimum[$series]) {
    fwrite(STDERR, "PHP_SECURITY_GATE=FAIL_VULNERABLE version=".PHP_VERSION."\n");
    exit(1);
}
echo "PHP_SECURITY_GATE=PASS version=".PHP_VERSION."\n";
'
# CLI PHP passing cannot prove that HTTP traffic uses the same patched runtime.
echo "PHP_FPM_AND_OTHER_SAPIS=NOT_VERIFIED"
echo "PRODUCTION_SECURITY=NOT_ATTESTED"
