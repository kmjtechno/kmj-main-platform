<?php

declare(strict_types=1);

// CI-only: a verified customer who owns an organization with an ACTIVE kmj-codebridge entitlement and
// one paired device/project with read/write/execute grants. No jobs are queued: the browser does that.
use App\Models\User;
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;

$root = $argv[1] ?? '';
$credential = $argv[2] ?? '';
$password = $argv[3] ?? '';
if (getenv('GITHUB_ACTIONS') !== 'true' || ! is_file($root.'/vendor/autoload.php') || strlen($credential) < 48 || strlen($password) < 20) {
    fwrite(STDERR, "BLOCKED: CI-only seed\n");
    exit(2);
}
require $root.'/vendor/autoload.php';
$app = require $root.'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();
if (DB::connection()->getDriverName() !== 'pgsql') {
    fwrite(STDERR, "BLOCKED: expected the disposable pgsql connection\n");
    exit(2);
}

$user = User::factory()->create([
    'email' => 'ci-ui-e2e@example.test', 'password' => Hash::make($password), 'email_verified_at' => now(),
]);
$org = $app->make(OrganizationCreator::class)->create('CI UI E2E Org', (int) $user->id);
$product = $app->make(ProductCatalog::class)->ensureSandboxProduct('kmj-codebridge', 'KMJ CodeBridge');
$policy = $app->make(EntitlementPolicyRegistry::class)->ensure($product->getKey(), 'ci.ui.e2e', 'ci.ui.e2e.access');
$app->make(EntitlementIssuer::class)->issue($org->getKey(), $policy, 'ci-ui-e2e:'.$org->getKey());

$tenant = (string) $org->getKey();
$device = 'ci-ui-desk';
$project = 'ci-roundtrip-proj';
$license = (string) Str::uuid();
$activation = (string) Str::uuid();
$now = now();
DB::table('kslp_licenses')->insert([
    'id' => $license, 'customer_id' => $tenant, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'professional',
    'status' => 'active', 'sequence' => 1, 'starts_at' => $now->copy()->subDay(), 'expires_at' => $now->copy()->addYear(),
    'grace_until' => $now->copy()->addYear()->addDays(2), 'created_at' => $now, 'updated_at' => $now,
]);
DB::table('kslp_activations')->insert([
    'id' => $activation, 'license_id' => $license, 'server_identity' => 'codebridge-device:'.$device,
    'machine_identity_hash' => hash('sha256', $device), 'idempotency_key' => 'ci-ui-e2e:'.$device,
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
echo json_encode(['tenant' => $tenant, 'device' => $device, 'project' => $project, 'email' => $user->email], JSON_THROW_ON_ERROR), "\n";
