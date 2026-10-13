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

    public function test_circular_failover_references_are_rejected(): void
    {
        config()->set('mail.default', 'loop');
        config()->set('mail.mailers.loop', ['transport' => 'failover', 'mailers' => ['loop']]);

        self::assertFalse(app(RegistrationMailReadiness::class)->canAttemptDelivery());
    }
}
