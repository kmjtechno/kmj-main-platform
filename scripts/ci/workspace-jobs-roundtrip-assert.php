<?php

declare(strict_types=1);

// CI-only: asserts the durable state left by the real device worker. Exit 0 only on full PASS.
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\DB;

$root = $argv[1] ?? '';
$tenant = $argv[2] ?? '';
require $root.'/vendor/autoload.php';
$app = require $root.'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();

$fail = [];
$jobs = DB::table('codebridge_workspace_jobs')->where('tenant_id', $tenant)->orderBy('created_at')->get();
if ($jobs->count() !== 3) {
    $fail[] = 'expected 3 jobs, got '.$jobs->count();
}
foreach ($jobs as $job) {
    $row = (array) $job;
    $tool = (string) $row['tool'];
    if ($row['status'] !== 'succeeded') {
        $fail[] = "$tool status={$row['status']} error={$row['error_code']}";
    }
    $kinds = DB::table('codebridge_workspace_job_events')->where('job_id', $row['id'])->orderBy('seq')->pluck('kind')->all();
    if (array_slice($kinds, -2) !== ['started', 'succeeded'] && ! in_array('succeeded', $kinds, true)) {
        $fail[] = "$tool events=".json_encode($kinds);
    }
    $evidence = json_decode((string) ($row['evidence'] ?? 'null'), true);
    if (! is_array($evidence) || ($evidence['result'] ?? null) !== 'pass') {
        $fail[] = "$tool evidence=".json_encode($evidence);
    }
    if ($tool === 'quality_gate' && (($evidence['gate'] ?? null) !== 'fast' || ($evidence['exit_code'] ?? null) !== 0)) {
        $fail[] = 'quality_gate evidence mismatch '.json_encode($evidence);
    }
    if ($row['claim_hash'] !== null && preg_match('/\A[0-9a-f]{64}\z/', (string) $row['claim_hash']) !== 1) {
        $fail[] = "$tool claim_hash malformed";
    }
    echo "JOB tool=$tool status={$row['status']} events=".implode(',', $kinds).' evidence='.json_encode($evidence)."\n";
}
if ($fail !== []) {
    echo 'WORKSPACE_JOBS_ROUNDTRIP=FAIL '.json_encode($fail)."\n";
    exit(1);
}
echo "WORKSPACE_JOBS_ROUNDTRIP_DB_ASSERT=PASS\n";
