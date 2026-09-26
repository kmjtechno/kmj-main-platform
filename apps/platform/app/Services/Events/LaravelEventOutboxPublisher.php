<?php

namespace App\Services\Events;

use App\Contracts\Events\OutboxPublisher;
use App\Events\DomainOutboxPublished;
use App\Models\DomainOutboxMessage;
use Illuminate\Support\Facades\Event;

final class LaravelEventOutboxPublisher implements OutboxPublisher
{
    public function publish(DomainOutboxMessage $message): void
    {
        Event::dispatch(new DomainOutboxPublished($message));
    }
}
