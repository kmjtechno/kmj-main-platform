<?php

namespace App\Contracts\Events;

use App\Models\DomainOutboxMessage;

interface OutboxPublisher
{
    public function publish(DomainOutboxMessage $message): void;
}
