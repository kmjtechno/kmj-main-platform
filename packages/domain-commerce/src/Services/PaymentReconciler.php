<?php

namespace KMJ\MainPlatform\Commerce\Services;

use DomainException;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Contracts\PaymentProviderAdapter;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;

final class PaymentReconciler
{
    public function __construct(private readonly CommercialOrderService $orders) {}

    public function reconcileConfirmed(
        string $orderId,
        int $actorUserId,
        PaymentProviderAdapter $adapter,
        string $providerReference,
    ): CommercialOrder {
        $orderId = trim($orderId);
        $providerReference = trim($providerReference);
        $provider = strtolower(trim($adapter->provider()));

        if ($orderId === '' || $actorUserId < 1 || $providerReference === '') {
            throw new InvalidArgumentException('Order, actor and provider reference are required.');
        }

        if (! preg_match('/^[a-z0-9][a-z0-9._-]{1,63}$/', $provider)) {
            throw new InvalidArgumentException('Adapter returned an invalid provider identifier.');
        }

        $confirmation = $adapter->confirmation($providerReference);

        if ($confirmation->provider !== $provider || $confirmation->reference !== $providerReference) {
            throw new DomainException('Provider confirmation evidence does not match the requested payment reference.');
        }

        return $this->orders->confirm(
            $orderId,
            $actorUserId,
            $confirmation->currency,
            $confirmation->amountMinor,
            $provider.':'.$confirmation->reference,
        );
    }
}
