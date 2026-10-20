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
const user = read('app/Models/User.php');
const mailConfig = read('config/mail.php');
const forgotUi = read('resources/js/pages/auth/forgot-password.tsx');
const publicShared = read('app/Http/Middleware/HandleInertiaRequests.php');
const publicHeader = read('resources/js/components/public-site-header.tsx');

void test('production registration is blocked before creating an unverifiable account', () => {
    assert.match(registration, /app\(\)->isProduction\(\)/);
    assert.match(registration, /canAttemptDelivery\(\)/);
    assert.ok(
        registration.indexOf('canAttemptDelivery()') <
            registration.indexOf('DB::transaction('),
    );
});

void test('log and array transports never count as external mail delivery', () => {
    assert.match(readiness, /'log', 'array'/);
    assert.match(readiness, /'failover', 'roundrobin'/);
    assert.match(readiness, /'hello@example.com'/);
});

void test('verification page never claims that an email arrived', () => {
    assert.match(views, /'mailDeliveryAvailable'/);
    assert.match(verifyUi, /Delivery is/);
    assert.match(
        verifyUi,
        /disabled=\{\s*processing\s*\|\|\s*!mailDeliveryAvailable\s*\}/,
    );
    assert.doesNotMatch(verifyUi, /has been sent to the email address/);
});

void test('new production signups are disabled when email cannot be delivered', () => {
    assert.match(views, /'registrationAvailable'/);
    assert.match(
        registerUi,
        /disabled=\{\s*processing\s*\|\|\s*!registrationAvailable\s*\}/,
    );
});

void test('public desktop and mobile registration CTAs respect production mail readiness', () => {
    assert.match(publicShared, /'registration_available'/);
    assert.match(publicShared, /! app\(\)->isProduction\(\)/);
    assert.match(publicShared, /RegistrationMailReadiness::class/);
    assert.match(publicShared, /canAttemptDelivery\(\)/);
    assert.match(publicHeader, /publicSite\?\.registration_available === true/);
    assert.equal(
        (publicHeader.match(/registrationAvailable \? \(/g) ?? []).length,
        2,
    );
    assert.equal(
        (publicHeader.match(/href=\{register\(\)\}/g) ?? []).length,
        2,
    );
    assert.equal((publicHeader.match(/Registration paused/g) ?? []).length, 2);
    assert.doesNotMatch(publicHeader, /href=\{register\(\)\}[\s\S]*?disabled=/);
});

void test('mail doctor never prints credentials or verification URLs', () => {
    assert.match(doctor, /kmj:mail:doctor/);
    assert.match(doctor, /can_attempt_external_delivery/);
    assert.doesNotMatch(
        doctor,
        /MAIL_PASSWORD|MAIL_USERNAME|verification\.verify/,
    );
});

void test('Fortify resend endpoint does not claim success for production log transport', () => {
    assert.match(user, /sendEmailVerificationNotification\(\)/);
    assert.match(user, /app\(\)->isProduction\(\)/);
    assert.match(user, /canAttemptDelivery\(\)/);
    assert.match(user, /ValidationException::withMessages/);
    assert.match(verifyUi, /errors\.email/);
});

void test('reset emails cannot claim sent with log-only production mail', () => {
    assert.match(user, /sendPasswordResetNotification/);
    assert.match(user, /canAttemptDelivery\(\)/);
    assert.match(views, /'mailDeliveryAvailable'/);
    assert.match(
        forgotUi,
        /disabled=\{\s*processing\s*\|\|\s*!mailDeliveryAvailable\s*\}/,
    );
    assert.match(forgotUi, /Inbox delivery is\s+not\s+confirmed/);
});

void test('temporary free relay is explicitly disabled, requires SMTPS credentials and remains replaceable', () => {
    assert.match(mailConfig, /'kmj_brevo' => \[/);
    assert.match(mailConfig, /'scheme' => 'smtps'/);
    assert.match(mailConfig, /'host' => 'smtp-relay\.brevo\.com'/);
    assert.match(mailConfig, /'port' => 465/);
    assert.match(mailConfig, /'KMJ_BREVO_SMTP_KEY'/);
    assert.match(mailConfig, /'KMJ_BREVO_ACTIVATED', false/);
    assert.match(readiness, /'kmj_requires_credentials'/);
    assert.match(readiness, /'kmj_activation_confirmed'/);
    assert.match(readiness, /kmj_required_sender_domain/);
    assert.match(readiness, /\$mailer\['scheme'\]/);
    assert.match(mailConfig, /'default' => env\('MAIL_MAILER', 'log'\)/);
    assert.doesNotMatch(mailConfig, /[a-zA-Z0-9]{20,}@smtp-brevo\.com/);
});

void test('customer signup collects only essential service contact and business context with server validation', () => {
    const profile = read('app/Models/CustomerProfile.php');
    const migration = read(
        'database/migrations/2026_10_20_070000_create_customer_profiles_table.php',
    );
    for (const marker of [
        "'account_type'",
        "'phone'",
        "'country'",
        "'company_name'",
        "'service_interest'",
    ]) {
        assert.ok(
            registerUi.includes('name=' + marker.replaceAll("'", '"')) ||
                registerUi.includes(marker.replaceAll("'", '"')),
            marker,
        );
        assert.ok(registration.includes(marker), marker);
        assert.ok(migration.includes(marker), marker);
    }
    assert.match(registerUi, /accountType === 'business'/);
    assert.match(registerUi, /billing addresses, tax IDs and/);
    assert.match(
        registration,
        /DB::transaction\(function \(\) use \(\$validated\)/,
    );
    assert.match(registration, /CustomerProfile::query\(\)->create/);
    assert.match(migration, /cascadeOnDelete\(\)/);
    assert.doesNotMatch(profile, /password|passkey|license|entitlement/i);
});
