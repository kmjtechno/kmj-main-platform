<?php

namespace App\Notifications;

use App\Services\Mail\WorkforceMailCatalog;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Notifications\Messages\MailMessage;
use Illuminate\Notifications\Notification;

/**
 * Self-addressed, explicitly labelled test notice only.
 * No authorization to send to another member or connected Gmail account.
 */
final class WorkforceMailPreviewNotification extends Notification implements ShouldQueue
{
    use Queueable;

    public function __construct(
        public readonly string $kind,
        public readonly string $audience,
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

        return WorkforceMailCatalog::previewMessage(
            $this->kind,
            $this->audience,
            is_string($name) && trim($name) !== '' ? $name : 'there',
        );
    }
}
