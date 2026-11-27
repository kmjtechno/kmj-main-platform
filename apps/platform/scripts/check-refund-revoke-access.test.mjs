import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) =>
    readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

void test('revoking access after a refund is explicit, owner-only and never part of recording a refund', () => {
    const recorder = read('app/Services/Commerce/OrderRefundRecorder.php');
    assert.doesNotMatch(recorder, /EntitlementRevoker|Entitlement::/);
    const revoker = read('app/Services/Commerce/RefundEntitlementRevoker.php');
    assert.match(revoker, /ENTITLEMENT_REVOKE_AFTER_REFUND/);
    assert.match(revoker, /REFUND_REVOKE_REFUND_RECORD_REQUIRED/);
    assert.match(revoker, /REFUND_REVOKE_OTHER_PAID_ORDER_EXISTS/);
    assert.match(revoker, /order\.refund\.entitlement_revoke/);
    const routes = read('routes/web.php');
    assert.match(
        routes,
        /refund-revoke-access'[\s\S]*?middleware\('password\.confirm'\)/,
    );
});

void test('the Super Admin button asks for confirmation and states a refund alone does not revoke', () => {
    const page = read('resources/js/pages/operator.tsx');
    assert.match(page, /revoke-access-after-refund/);
    assert.match(page, /window\.confirm/);
    assert.match(page, /A refund record alone does not do this/);
});
