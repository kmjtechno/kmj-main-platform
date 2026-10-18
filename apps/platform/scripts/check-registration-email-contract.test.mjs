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
        /disabled=\{processing \|\| !mailDeliveryAvailable\}/,
    );
    assert.doesNotMatch(verifyUi, /has been sent to the email address/);
});

void test('new production signups are disabled when email cannot be delivered', () => {
    assert.match(views, /'registrationAvailable'/);
    assert.match(
        registerUi,
        /disabled=\{processing \|\| !registrationAvailable\}/,
    );
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
        /disabled=\{processing \|\| !mailDeliveryAvailable\}/,
    );
    assert.match(forgotUi, /Inbox delivery is not confirmed/);
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
