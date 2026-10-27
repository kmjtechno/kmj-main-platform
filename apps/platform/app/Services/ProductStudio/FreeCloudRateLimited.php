<?php

namespace App\Services\ProductStudio;

use RuntimeException;

final class FreeCloudRateLimited extends RuntimeException
{
    public function __construct(public readonly int $retryAfter)
    {
        parent::__construct('FREE_CLOUD_RATE_LIMITED');
    }
}
