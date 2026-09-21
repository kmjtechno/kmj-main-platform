<?php

namespace Tests\Feature;

use Tests\TestCase;

final class StagingMonitoringTest extends TestCase
{
    public function test_monitor_is_hidden_outside_staging(): void
    {
        $this->get('/info')->assertNotFound();
        $this->getJson('/info/status')->assertNotFound();
    }

    public function test_monitor_is_not_public_on_exact_staging_host(): void
    {
        $this->get('https://staging.kmjtechno.com/info')->assertNotFound();
        $this->getJson('https://staging.kmjtechno.com/info/status')->assertNotFound();
    }

    public function test_monitor_is_hidden_on_production_and_similar_hosts(): void
    {
        foreach ([
            'kmjtechno.com',
            'www.kmjtechno.com',
            'staging.kmjtechno.com.example.test',
            'other.kmjtechno.com',
        ] as $host) {
            $this->get('https://'.$host.'/info')->assertNotFound();
            $this->getJson('https://'.$host.'/info/status')->assertNotFound();
        }
    }

    public function test_forwarded_host_cannot_restore_public_monitoring(): void
    {
        $headers = ['X-Forwarded-Host' => 'staging.kmjtechno.com'];

        $this->get('https://kmjtechno.com/info', $headers)->assertNotFound();
        $this->getJson('https://kmjtechno.com/info/status', $headers)->assertNotFound();
    }
}
