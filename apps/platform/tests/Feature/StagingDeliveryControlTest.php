<?php

namespace Tests\Feature;

use Tests\TestCase;

final class StagingDeliveryControlTest extends TestCase
{
    public function test_public_staging_status_does_not_expose_delivery_state(): void
    {
        $this->getJson('https://staging.kmjtechno.com/info/status')
            ->assertNotFound();
    }
}
