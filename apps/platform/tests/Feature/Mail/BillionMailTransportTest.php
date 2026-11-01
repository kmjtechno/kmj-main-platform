<?php

namespace Tests\Feature\Mail;

use App\Services\Mail\RegistrationMailReadiness;
use Tests\TestCase;

final class BillionMailTransportTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        config()->set('mail.default', 'kmj_billionmail');
        config()->set('mail.from.address', 'no-reply@kmjtechno.com');
        config()->set('mail.mailers.kmj_billionmail', [
            'transport' => 'smtp',
            'scheme' => 'smtps',
            'host' => 'mail.example.test',
            'port' => 465,
            'username' => null,
            'password' => null,
            'kmj_requires_credentials' => true,
            'kmj_required_sender_domain' => 'kmjtechno.com',
            'kmj_activation_confirmed' => false,
        ]);
    }

    public function test_mailer_is_explicitly_opt_in(): void
    {
        $this->assertFalse((new RegistrationMailReadiness)->canAttemptDelivery());
    }

    public function test_activation_without_credentials_is_blocked(): void
    {
        config()->set('mail.mailers.kmj_billionmail.kmj_activation_confirmed', true);

        $this->assertFalse((new RegistrationMailReadiness)->canAttemptDelivery());
    }

    public function test_wrong_sender_domain_is_blocked(): void
    {
        $this->configureCredentials();
        config()->set('mail.from.address', 'no-reply@another.example');

        $this->assertFalse((new RegistrationMailReadiness)->canAttemptDelivery());
    }

    public function test_insecure_or_unexpected_port_is_blocked(): void
    {
        $this->configureCredentials();

        config()->set('mail.mailers.kmj_billionmail.scheme', 'smtp');
        $this->assertFalse((new RegistrationMailReadiness)->canAttemptDelivery());

        config()->set('mail.mailers.kmj_billionmail.scheme', 'smtps');
        config()->set('mail.mailers.kmj_billionmail.port', 587);
        $this->assertFalse((new RegistrationMailReadiness)->canAttemptDelivery());
    }

    public function test_ready_configuration_only_permits_an_attempt_and_never_sends(): void
    {
        $this->configureCredentials();

        // No real SMTP connection or delivery assertion: an independent
        // staging-and-inbox test must still authorize production activation.
        $this->assertTrue((new RegistrationMailReadiness)->canAttemptDelivery());
    }

    private function configureCredentials(): void
    {
        config()->set('mail.mailers.kmj_billionmail.kmj_activation_confirmed', true);
        config()->set('mail.mailers.kmj_billionmail.username', 'relay@kmjtechno.com');
        config()->set('mail.mailers.kmj_billionmail.password', str_repeat('x', 24));
    }
}
