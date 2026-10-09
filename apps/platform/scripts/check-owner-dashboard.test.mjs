import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const routes = readFileSync('routes/web.php', 'utf8');
const dashboard = readFileSync('resources/js/pages/dashboard.tsx', 'utf8');
const access = readFileSync('app/Services/PlatformOwnerAccess.php', 'utf8');

void test('server derives owner controls from the verified role guard', () => {
    assert.ok(
        routes.includes(
            "'canManageCodeBridgeOwnerPlan' => app(PlatformOwnerAccess::class)->allows($user)",
        ),
    );
    assert.ok(access.includes("getAttribute('is_platform_owner')"));
    assert.ok(access.includes('hasVerifiedEmail()'));
    assert.ok(access.includes('passkeys()->exists()'));
});

void test('owner controls are conditional and point to the guarded route', () => {
    assert.match(
        dashboard,
        /canManageOwnerPlan=\{\s*canManageCodeBridgeOwnerPlan\s*\}/,
    );
    assert.ok(dashboard.includes('{canManageOwnerPlan && ('));
    assert.ok(dashboard.includes('href="/operator/codebridge/owner-plan"'));
    assert.ok(dashboard.includes('Owner plan controls'));
});

void test('plan display remains bound to the actual license value', () => {
    assert.ok(dashboard.includes('detail?.plan'));
    assert.ok(dashboard.includes('titleCase(detail.plan)'));
    assert.ok(!dashboard.includes("plan: 'owner'"));
});
