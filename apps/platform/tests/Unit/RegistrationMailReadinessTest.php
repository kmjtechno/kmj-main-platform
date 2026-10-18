<?php

namespace Tests\Unit;

use App\Services\Mail\RegistrationMailReadiness;
use Tests\TestCase;

final class RegistrationMailReadinessTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        config()->set('mail.from.address', 'no-reply@kmjtechno.com');
    }

    public function test_log_and_array_mailers_are_not_external_delivery(): void
    {
        foreach (['log', 'array'] as $name) {
            config()->set('mail.default', $name);
            self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
        }
    }

    public function test_failover_to_log_is_not_counted_as_successful_external_delivery(): void
    {
        config()->set('mail.default', 'failover');
        config()->set('mail.mailers.failover', ['transport' => 'failover', 'mailers' => ['smtp', 'log']]);
        config()->set('mail.mailers.smtp', ['transport' => 'smtp', 'host' => 'smtp.example.net', 'port' => 587]);

        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }

    public function test_usable_smtp_configuration_is_eligible_but_not_proof_of_delivery(): void
    {
        config()->set('mail.default', 'smtp');
        config()->set('mail.mailers.smtp', ['transport' => 'smtp', 'host' => 'smtp.example.net', 'port' => 587]);

        self::assertTrue(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }

    public function test_example_localhost_smtp_is_not_accepted_as_a_production_delivery_provider(): void
    {
        config()->set('mail.default', 'smtp');
        config()->set('mail.mailers.smtp', ['transport' => 'smtp', 'host' => '127.0.0.1', 'port' => 2525]);

        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }

    public function test_invalid_smtp_port_fails_closed(): void
    {
        config()->set('mail.default', 'smtp');

        foreach ([0, -1, 65536] as $port) {
            config()->set('mail.mailers.smtp', [
                'transport' => 'smtp', 'host' => '127.0.0.1', 'port' => $port,
            ]);
            self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
        }
    }

    public function test_local_relay_must_accept_a_loopback_connection(): void
    {
        $listener = stream_socket_server('tcp://127.0.0.1:0', $errorCode, $errorMessage);

        self::assertIsResource($listener);

        $address = stream_socket_get_name($listener, false);
        self::assertIsString($address);

        $port = (int) preg_replace('/^.*:/', '', $address);
        self::assertGreaterThan(0, $port);

        config()->set('mail.default', 'smtp');
        config()->set('mail.mailers.smtp', [
            'transport' => 'smtp', 'host' => '127.0.0.1', 'port' => $port,
        ]);

        try {
            self::assertTrue(app(RegistrationMailReadiness::class)->canAttemptDelivery());
        } finally {
            fclose($listener);
        }

        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }

    public function test_example_sender_and_missing_mailers_are_rejected(): void
    {
        config()->set('mail.default', 'smtp');
        config()->set('mail.mailers.smtp', ['transport' => 'smtp', 'host' => 'smtp.example.net', 'port' => 587]);
        config()->set('mail.from.address', 'hello@example.com');
        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());

        config()->set('mail.from.address', 'no-reply@kmjtechno.com');
        config()->set('mail.default', 'missing');
        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }

    public function test_temporary_free_smtp_requires_credentials_approval_and_matching_sender(): void
    {
        config()->set('mail.default', 'kmj_brevo');
        config()->set('mail.mailers.kmj_brevo', [
            'transport' => 'smtp',
            'scheme' => 'smtps',
            'host' => 'smtp-relay.brevo.com',
            'port' => 465,
            'username' => null,
            'password' => null,
            'kmj_requires_credentials' => true,
            'kmj_required_sender_domain' => 'kmjtechno.com',
            'kmj_activation_confirmed' => false,
        ]);

        $service = app(RegistrationMailReadiness::class);
        self::assertFalse($service->canAttemptDelivery());

        config()->set('mail.mailers.kmj_brevo.kmj_activation_confirmed', true);
        self::assertFalse($service->canAttemptDelivery());

        config()->set('mail.mailers.kmj_brevo.username', 'relay@smtp-brevo.com');
        config()->set('mail.mailers.kmj_brevo.password', 'test-only-not-a-real-secret');
        self::assertTrue($service->canAttemptDelivery());

        config()->set('mail.from.address', 'no-reply@unapproved.example');
        self::assertFalse($service->canAttemptDelivery());

        config()->set('mail.from.address', 'no-reply@kmjtechno.com');
        config()->set('mail.mailers.kmj_brevo.scheme', 'smtp');
        self::assertFalse($service->canAttemptDelivery());
    }

    public function test_circular_failover_references_are_rejected(): void
    {
        config()->set('mail.default', 'loop');
        config()->set('mail.mailers.loop', ['transport' => 'failover', 'mailers' => ['loop']]);

        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }
}
