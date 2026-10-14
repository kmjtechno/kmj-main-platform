import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');
const readiness = read('app/Services/Mail/RegistrationMailReadiness.php');
const registration = read('app/Actions/Fortify/CreateNewUser.php');
const views = read('app/Providers/FortifyServiceProvider.php');
const verifyUi = read('resources/js/pages/auth/verify-email.tsx');
const registerUi = read('resources/js/pages/auth/register.tsx');
const doctor = read('app/Console/Commands/RegistrationMailDoctorCommand.php');

void test('production registration is blocked before creating an unverifiable account', () => {
    assert.match(registration, /app\(\)->isProduction\(\)/);
    assert.match(registration, /canAttemptDelivery\(\)/);
    assert.ok(registration.indexOf('canAttemptDelivery()') < registration.indexOf('DB::transaction('));
});

void test('log and array transports never count as external mail delivery', () => {
    assert.match(readiness, /'log', 'array'/);
    assert.match(readiness, /'failover', 'roundrobin'/);
    assert.match(readiness, /'hello@example.com'/);
});

void test('verification page never claims that an email arrived', () => {
    assert.match(views, /'mailDeliveryAvailable'/);
    assert.match(verifyUi, /Delivery is/);
    assert.match(verifyUi, /disabled=\{processing \|\| !mailDeliveryAvailable\}/);
    assert.doesNotMatch(verifyUi, /has been sent to the email address/);
});

void test('new production signups are disabled when email cannot be delivered', () => {
    assert.match(views, /'registrationAvailable'/);
    assert.match(registerUi, /disabled=\{processing \|\| !registrationAvailable\}/);
});

void test('mail doctor never prints credentials or verification URLs', () => {
    assert.match(doctor, /kmj:mail:doctor/);
    assert.match(doctor, /can_attempt_external_delivery/);
    assert.doesNotMatch(doctor, /MAIL_PASSWORD|MAIL_USERNAME|verification\.verify/);
});
