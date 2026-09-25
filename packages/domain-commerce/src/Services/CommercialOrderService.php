<?php

namespace KMJ\MainPlatform\Commerce\Services;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Commerce\Contracts\DomainEventRecorder;
use KMJ\MainPlatform\Commerce\Models\CommercialLedgerEntry;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;

final class CommercialOrderService
{
    public function __construct(private readonly DomainEventRecorder $events) {}

    public function request(
        string $organizationId,
        string $productId,
        int $requesterUserId,
        string $idempotencyKey,
    ): CommercialOrder {
        $organizationId = trim($organizationId);
        $productId = trim($productId);
        $idempotencyKey = trim($idempotencyKey);

        if ($organizationId === '' || $productId === '' || $requesterUserId < 1 || $idempotencyKey === '') {
            throw new InvalidArgumentException('Organization, product, requester and idempotency key are required.');
        }

        return DB::transaction(function () use ($organizationId, $productId, $requesterUserId, $idempotencyKey): CommercialOrder {
            $order = CommercialOrder::query()->firstOrCreate(
                ['idempotency_key' => $idempotencyKey],
                [
                    'organization_id' => $organizationId,
                    'product_id' => $productId,
                    'requester_user_id' => $requesterUserId,
                    'status' => 'requested',
                ],
            );

            $this->assertRequestMatches($order, $organizationId, $productId, $requesterUserId);

            if ($order->wasRecentlyCreated) {
                $this->record($order, $requesterUserId, 'commerce.order.requested', [
                    'product_id' => $productId,
                    'status' => 'requested',
                ]);
            }

            return $order;
        });
    }

    public function confirm(
        string $orderId,
        int $actorUserId,
        string $currency,
        int $amountMinor,
        string $confirmationReference,
    ): CommercialOrder {
        $currency = strtoupper(trim($currency));
        $confirmationReference = trim($confirmationReference);

        if ($orderId === '' || $actorUserId < 1 || $amountMinor < 1 || ! preg_match('/^[A-Z]{3}$/', $currency) || $confirmationReference === '') {
            throw new InvalidArgumentException('A valid order, actor, currency, positive amount and confirmation reference are required.');
        }

        return DB::transaction(function () use ($orderId, $actorUserId, $currency, $amountMinor, $confirmationReference): CommercialOrder {
            $order = CommercialOrder::query()->lockForUpdate()->findOrFail($orderId);

            if ($order->status === 'confirmed') {
                $this->assertConfirmationMatches($order, $currency, $amountMinor, $confirmationReference);

                return $order;
            }

            if ($order->status !== 'requested') {
                throw new DomainException('Only a requested commercial order can be confirmed.');
            }

            if (CommercialOrder::query()
                ->where('confirmation_reference', $confirmationReference)
                ->whereKeyNot($order->getKey())
                ->exists()) {
                throw new DomainException('Confirmation reference is already attached to another commercial order.');
            }

            $order->forceFill([
                'status' => 'confirmed',
                'currency' => $currency,
                'amount_minor' => $amountMinor,
                'confirmation_reference' => $confirmationReference,
                'confirmed_at' => now(),
            ])->save();

            $this->record($order, $actorUserId, 'commerce.order.confirmed', [
                'currency' => $currency,
                'amount_minor' => $amountMinor,
                'confirmation_reference' => $confirmationReference,
                'status' => 'confirmed',
            ]);

            return $order->refresh();
        });
    }

    public function cancel(string $orderId, int $actorUserId, ?string $reason = null): CommercialOrder
    {
        $reason = $reason === null ? null : trim($reason);

        if ($orderId === '' || $actorUserId < 1) {
            throw new InvalidArgumentException('A valid order and actor are required.');
        }

        return DB::transaction(function () use ($orderId, $actorUserId, $reason): CommercialOrder {
            $order = CommercialOrder::query()->lockForUpdate()->findOrFail($orderId);

            if ($order->status === 'cancelled') {
                return $order;
            }

            if ($order->status !== 'requested') {
                throw new DomainException('Only a requested commercial order can be cancelled.');
            }

            $order->forceFill([
                'status' => 'cancelled',
                'cancelled_at' => now(),
            ])->save();

            $this->record($order, $actorUserId, 'commerce.order.cancelled', [
                'reason' => $reason,
                'status' => 'cancelled',
            ]);

            return $order->refresh();
        });
    }

    private function assertRequestMatches(
        CommercialOrder $order,
        string $organizationId,
        string $productId,
        int $requesterUserId,
    ): void {
        if (
            $order->organization_id !== $organizationId
            || $order->product_id !== $productId
            || $order->requester_user_id !== $requesterUserId
        ) {
            throw new DomainException('Idempotency key was already used for a different commercial order request.');
        }
    }

    private function assertConfirmationMatches(
        CommercialOrder $order,
        string $currency,
        int $amountMinor,
        string $confirmationReference,
    ): void {
        if (
            $order->currency !== $currency
            || $order->amount_minor !== $amountMinor
            || $order->confirmation_reference !== $confirmationReference
        ) {
            throw new DomainException('Confirmed order cannot be replayed with different commercial facts.');
        }
    }

    /** @param array<string, mixed> $payload */
    private function record(CommercialOrder $order, ?int $actorUserId, string $eventType, array $payload): void
    {
        $ledger = CommercialLedgerEntry::query()->create([
            'order_id' => $order->getKey(),
            'organization_id' => $order->organization_id,
            'actor_user_id' => $actorUserId,
            'event_type' => $eventType,
            'payload' => $payload,
            'occurred_at' => now(),
        ]);

        $this->events->recordDomainEvent(
            eventType: $eventType,
            aggregateType: 'commercial_order',
            aggregateId: (string) $order->getKey(),
            organizationId: (string) $order->organization_id,
            payload: [
                'ledger_sequence' => (int) $ledger->getKey(),
                'actor_user_id' => $actorUserId,
                'facts' => $payload,
            ],
            idempotencyKey: 'commerce-ledger:'.$ledger->getKey(),
            occurredAt: $ledger->occurred_at,
        );
    }
}
