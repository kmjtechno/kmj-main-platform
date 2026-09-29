<?php

namespace App\Events;

use App\Models\DomainOutboxMessage;

final readonly class DomainOutboxPublished
{
    public function __construct(public DomainOutboxMessage $message) {}
}
