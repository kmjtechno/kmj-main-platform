import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const operator = readFileSync('resources/js/pages/operator.tsx', 'utf8');
const web = readFileSync('routes/web.php', 'utf8');

void test('owner order list can only RECORD a refund (no money movement, no license change)', () => {
    assert.match(operator, /function RefundRecord\(/);
    assert.match(
        operator,
        /\/operator\/orders\/\$\{order\.id\}\/refund-record/,
    );
    assert.match(
        operator,
        /does not send money, change the\s+order, or revoke the license/,
    );
    assert.doesNotMatch(operator, /refund-record[\s\S]{0,200}(revoke|fulfill)/);
});

void test('refund form converts normal units to integer minor units and caps at remaining', () => {
    assert.match(
        operator,
        /toMinorUnits\(form\.data\.amount_minor, currency\)/,
    );
    assert.match(operator, /minor > remaining/);
    assert.match(operator, /crypto\.randomUUID\(\)/);
});

void test('refund record is only offered for confirmed orders with remaining amount', () => {
    assert.match(
        operator,
        /order\.status === 'confirmed' &&[\s\S]{0,300}order\.refunded_minor\s*<\s*order\.amount_minor/,
    );
});

void test('route is password-confirmed and handled by the invokable controller', () => {
    assert.match(
        web,
        /Route::post\('operator\/orders\/\{order\}\/refund-record', OrderRefundRecordController::class\)\s*->name\('operator\.orders\.refund-record'\)->middleware\('password\.confirm'\)/,
    );
    assert.match(
        web,
        /'refunded_minor' => \(int\) DB::table\('commerce_order_refund_records'\)/,
    );
});
