<?php

/*
 * CI-only fixture for scripts/ui-smoke.mjs (dashboard mode).
 *
 * Creates one verified customer, an organization they own, an active CodeBridge
 * licence and an active kmj-codebridge entitlement, mirroring the fixture used by
 * tests/Feature/CodeBridgeAdminHttpTest.php. Run against a throwaway database only:
 *
 *   php artisan tinker --execute="require base_path('scripts/ci-seed-ui-smoke.php');"
 */

use App\Models\User;
use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;

$tenant = (string) Str::uuid();
$now = now();

$user = User::factory()->create([
    'email' => 'ui-smoke@example.test',
    'email_verified_at' => $now,
]);

DB::table('organizations')->insert([
    'id' => $tenant,
    'name' => 'KMJ UI Smoke Organization',
    'created_at' => $now,
    'updated_at' => $now,
]);
DB::table('organization_memberships')->insert([
    'id' => (string) Str::uuid(),
    'organization_id' => $tenant,
    'user_id' => $user->id,
    'role' => 'owner',
    'created_at' => $now,
    'updated_at' => $now,
]);

$license = (string) Str::uuid();
DB::table('kslp_licenses')->insert([
    'id' => $license,
    'customer_id' => $tenant,
    'product' => 'KMJ_CODEBRIDGE',
    'plan' => 'professional',
    'status' => 'active',
    'sequence' => 1,
    'starts_at' => $now->copy()->subMinute(),
    'expires_at' => $now->copy()->addYear(),
    'grace_until' => $now->copy()->addYear()->addDays(2),
    'created_at' => $now,
    'updated_at' => $now,
]);

$legacyProduct = DB::table('products')->where('slug', 'codebridge')->value('id');
if (! $legacyProduct) {
    $legacyProduct = (string) Str::uuid();
    DB::table('products')->insert([
        'id' => $legacyProduct,
        'slug' => 'codebridge',
        'name' => 'CodeBridge',
        'status' => 'active',
        'lifecycle' => 'available',
        'is_public' => false,
        'sort_order' => 100,
        'purchase_enabled' => false,
        'licensing_enabled' => true,
        'created_at' => $now,
        'updated_at' => $now,
    ]);
    DB::table('plans')->insert([
        'id' => (string) Str::uuid(),
        'product_id' => $legacyProduct,
        'code' => 'codebridge.professional',
        'name' => 'CodeBridge Professional',
        'pricing_model' => 'license',
        'status' => 'active',
        'trial_days' => 0,
        'features' => json_encode(['read' => true]),
        'limits' => json_encode(['devices' => 2]),
        'created_at' => $now,
        'updated_at' => $now,
    ]);
}

$products = app(KmjProductCatalog::class)->syncAll();
$product = $products[KmjProductCatalog::CODEBRIDGE_SLUG];
$policy = app(EntitlementPolicyRegistry::class)->ensure(
    $product->getKey(),
    'codebridge.ui-smoke',
    'codebridge.service.access',
);
app(EntitlementIssuer::class)->issue($tenant, $policy, 'ui-smoke');

echo 'ui-smoke fixture ready for '.$user->email.PHP_EOL;
