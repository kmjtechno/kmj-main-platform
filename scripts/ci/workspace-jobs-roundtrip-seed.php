<?php

declare(strict_types=1);

// CI-only: seeds a disposable tenant/device/credential and queues three named jobs.
// Prints one JSON line {"tenant","credential","device","project","jobs":[...]} to STDOUT.
use App\Models\User;
use App\Services\CodeBridge\Workspace\WorkspaceJobService;
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

$root = $argv[1] ?? '';
$credential = $argv[2] ?? '';
if (getenv('GITHUB_ACTIONS') !== 'true' || ! is_file($root.'/vendor/autoload.php') || strlen($credential) < 48) {
    fwrite(STDERR, "BLOCKED: CI-only seed\n");
    exit(2);
}
require $root.'/vendor/autoload.php';
$app = require $root.'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();
if (DB::connection()->getDriverName() !== 'pgsql' || (string) config('database.connections.pgsql.host') === '' ) {
    fwrite(STDERR, "BLOCKED: expected the disposable pgsql connection\n");
    exit(2);
}

$device = 'ci-roundtrip-desk';
$project = 'ci-roundtrip-proj';
$tenant = (string) Str::uuid();
$license = (string) Str::uuid();
$activation = (string) Str::uuid();
$now = now();
DB::table('organizations')->insert(['id' => $tenant, 'name' => 'CI round-trip', 'created_at' => $now, 'updated_at' => $now]);
DB::table('kslp_licenses')->insert([
    'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional',
    'status' => 'active', 'sequence' => 1, 'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
    'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now,
]);
DB::table('kslp_activations')->insert([
    'id' => $activation, 'license_id' => $license, 'server_identity' => 'codebridge-device:'.$device,
    'machine_identity_hash' => hash('sha256', $device), 'idempotency_key' => 'ci-roundtrip:'.$device,
    'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now,
]);
DB::table('codebridge_device_credentials')->insert([
    'id' => (string) Str::uuid(), 'license_id' => $license, 'activation_id' => $activation, 'tenant_id' => $tenant,
    'device_id' => $device, 'server_identity' => 'codebridge-device:'.$device,
    'token_hash' => hash('sha256', $credential), 'lease_sequence' => 0, 'expires_at_epoch' => time() + 3600,
]);
DB::table('codebridge_device_pairings')->insert([
    'id' => (string) Str::uuid(), 'device_code_hash' => hash('sha256', 'device-code:'.$device),
    'user_code_hash' => hash('sha256', 'user-code:'.$device), 'device_id' => $device, 'device_name' => $device,
    'platform' => 'linux', 'arch' => 'x64', 'project_id' => $project, 'project_name' => $project,
    'requested_permissions' => json_encode(['read', 'write', 'execute']), 'code_challenge' => str_repeat('x', 43),
    'status' => 'consumed', 'tenant_id' => $tenant, 'license_id' => $license, 'activation_id' => $activation,
    'expires_at' => $now->copy()->addMinutes(5), 'consumed_at' => $now, 'created_at' => $now, 'updated_at' => $now,
]);
$user = User::factory()->create(['email_verified_at' => now()]);
$service = $app->make(WorkspaceJobService::class);
$jobs = [];
foreach ([['git_status', []], ['inspect_project', []], ['quality_gate', ['gate' => 'fast']]] as $i => [$tool, $args]) {
    $jobs[] = $service->enqueue($tenant, (int) $user->id, $device, $project, $tool, $args, 'ci-roundtrip-key-000'.$i)['id'];
}
echo json_encode(['tenant' => $tenant, 'device' => $device, 'project' => $project, 'jobs' => $jobs], JSON_THROW_ON_ERROR), "\n";
