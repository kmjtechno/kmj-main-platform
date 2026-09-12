<?php

namespace KMJ\MainPlatform\Commerce\ValueObjects;

use InvalidArgumentException;

final readonly class ProviderPaymentConfirmation
{
    public string $provider;

    public string $reference;

    public string $currency;

    public int $amountMinor;

    public function __construct(string $provider, string $reference, string $currency, int $amountMinor)
    {
        $provider = strtolower(trim($provider));
        $reference = trim($reference);
        $currency = strtoupper(trim($currency));

        if (! preg_match('/^[a-z0-9][a-z0-9._-]{1,63}$/', $provider)) {
            throw new InvalidArgumentException('A valid provider identifier is required.');
        }

        if ($reference === '' || strlen($reference) > 120) {
            throw new InvalidArgumentException('A valid provider confirmation reference is required.');
        }

        if (! preg_match('/^[A-Z]{3}$/', $currency) || $amountMinor < 0) {
            throw new InvalidArgumentException('A valid currency and non-negative amount are required.');
        }

        $this->provider = $provider;
        $this->reference = $reference;
        $this->currency = $currency;
        $this->amountMinor = $amountMinor;
    }
}
