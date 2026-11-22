<?php

namespace App\Services\Mail;

use App\Events\DomainOutboxPublished;
use App\Models\User;
use App\Notifications\BrandedCustomerNotification;
use Carbon\CarbonImmutable;
use Illuminate\Auth\Events\Verified;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Log;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use Throwable;

/**
 * Event-driven notification wiring, disabled unless an owner explicitly
 * enables KMJ_TRANSACTIONAL_NOTIFICATIONS_ENABLED after real mail acceptance.
 *
 * Commerce messages originate exclusively from the existing idempotent
 * domain outbox and authoritative persisted order state; not from browser
 * callbacks, untrusted webhook payloads, or preview catalog products.
 */
final class BrandedCustomerEvents
{
    public static function register(): void
    {
        Event::listen(Verified::class, static function (Verified $event): void {
            if (! self::ready() || ! $event->user instanceof User || ! $event->user->hasVerifiedEmail()) {
                return;
            }

            try {
                $event->user->notify(new BrandedCustomerNotification('welcome'));
            } catch (Throwable $exception) {
                // Verification must never be rolled back by an optional
                // welcome-mail failure. No exception message/PII in logs.
                Log::warning('kmj_transactional_welcome_enqueue_failed', [
                    'category' => $exception::class,
                ]);
            }
        });

        Event::listen(DomainOutboxPublished::class, static function (DomainOutboxPublished $event): void {
            if (! self::ready() || $event->message->aggregate_type !== 'commercial_order') {
                return;
            }

            $activatedAt = self::activatedAt();
            if ($activatedAt === null || $event->message->occurred_at === null
                || $event->message->occurred_at->lessThan($activatedAt)) {
                // Never replay old, unsent commerce outbox history into customer inboxes.
                return;
            }

            $kind = match ($event->message->event_type) {
                'commerce.order.requested' => 'order_received',
                'commerce.order.confirmed' => 'order_confirmed',
                'commerce.order.cancelled' => 'order_cancelled',
                default => null,
            };
            if ($kind === null) {
                return;
            }

            $order = CommercialOrder::query()->find($event->message->aggregate_id);
            if ($order === null) {
                return;
            }

            $expectedState = match ($kind) {
                'order_received' => 'requested',
                'order_confirmed' => 'confirmed',
                default => 'cancelled',
            };
            if ($order->status !== $expectedState) {
                // A historical outbox event must not send a stale status.
                return;
            }

            $user = User::query()->find($order->requester_user_id);
            $product = Product::query()->find($order->product_id);
            if ($user === null || ! $user->hasVerifiedEmail() || $product === null) {
                return;
            }

            $details = [
                'state' => $expectedState,
                'order' => (string) $order->getKey(),
                'product' => (string) $product->name,
            ];

            // Queued notifications share the outbox dispatcher transaction.
            // Only one publish of the event schedules the notification.
            $user->notify(new BrandedCustomerNotification($kind, $details));

            if ($kind === 'order_confirmed'
                && config('services.kmj_transactional_mail.send_payment_receipts', false) === true
                && is_int($order->amount_minor) && $order->amount_minor > 0
                && is_string($order->currency) && is_string($order->confirmation_reference)) {
                $user->notify(new BrandedCustomerNotification('payment_receipt', [
                    ...$details,
                    'amount_minor' => $order->amount_minor,
                    'currency' => $order->currency,
                    'reference' => $order->confirmation_reference,
                ]));
            }
        });
    }

    private static function ready(): bool
    {
        $activatedAt = self::activatedAt();

        return config('services.kmj_transactional_mail.enabled', false) === true
            && $activatedAt !== null
            && now()->greaterThanOrEqualTo($activatedAt)
            && app(RegistrationMailReadiness::class)->canAttemptDelivery();
    }

    private static function activatedAt(): ?CarbonImmutable
    {
        $value = config('services.kmj_transactional_mail.not_before', '');
        if (! is_string($value) || preg_match('/\\A\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z\\z/D', $value) !== 1) {
            return null;
        }

        try {
            return CarbonImmutable::parse($value, 'UTC');
        } catch (Throwable) {
            return null;
        }
    }
}
