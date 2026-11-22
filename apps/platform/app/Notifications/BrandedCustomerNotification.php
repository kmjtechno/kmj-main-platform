<?php

namespace App\Notifications;

use App\Services\Mail\BrandedCustomerMail;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Notifications\Messages\MailMessage;
use Illuminate\Notifications\Notification;

/**
 * Explicit, mail-only delivery adapter. The authoritative business workflow
 * must validate its facts before constructing a notification; presentation
 * cannot activate licenses, settle orders, or verify account emails.
 */
final class BrandedCustomerNotification extends Notification implements ShouldQueue
{
    use Queueable;

    /** @param array<string, mixed> $context */
    public function __construct(
        public readonly string $kind,
        public readonly array $context = [],
    ) {
        $this->afterCommit();
    }

    /** @return list<string> */
    public function via(object $notifiable): array
    {
        return ['mail'];
    }

    public function toMail(object $notifiable): MailMessage
    {
        $name = $notifiable->name ?? null;

        return BrandedCustomerMail::compose(
            $this->kind,
            is_string($name) && trim($name) !== '' ? $name : 'there',
            $this->context,
        );
    }
}
