<?php

namespace KMJ\MainPlatform\Commerce\Contracts;

use KMJ\MainPlatform\Commerce\ValueObjects\ProviderPaymentConfirmation;

interface PaymentProviderAdapter
{
    public function provider(): string;

    public function confirmation(string $providerReference): ProviderPaymentConfirmation;
}
