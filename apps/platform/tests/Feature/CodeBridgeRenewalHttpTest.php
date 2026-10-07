<?php

namespace Tests\Feature;

use Tests\TestCase;

final class CodeBridgeRenewalHttpTest extends TestCase
{
    public function test_renewal_is_unavailable_while_disabled(): void
    {
        config(['codebridge.enabled' => false]);

        $this->postJson('/api/v1/codebridge/renew', [])->assertStatus(503);
    }

    public function test_enabled_renewal_requires_a_device_credential(): void
    {
        config(['codebridge.enabled' => true]);

        $this->postJson('/api/v1/codebridge/renew', [])->assertUnauthorized();
        $this->withToken('short')->postJson('/api/v1/codebridge/renew', [])->assertUnauthorized();
    }

    public function test_oversized_renewal_is_rejected_before_database_access(): void
    {
        config(['codebridge.enabled' => true]);

        $this->withToken(str_repeat('a', 48))
            ->postJson('/api/v1/codebridge/renew', ['padding' => str_repeat('x', 4097)])
            ->assertStatus(413);
    }

    public function test_get_cannot_issue_a_lease(): void
    {
        config(['codebridge.enabled' => true]);

        $this->getJson('/api/v1/codebridge/renew')->assertStatus(405);
    }
}
