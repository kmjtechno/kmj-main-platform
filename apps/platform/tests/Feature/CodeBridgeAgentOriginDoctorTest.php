<?php

namespace Tests\Feature;

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class CodeBridgeAgentOriginDoctorTest extends TestCase
{
    public function test_missing_public_origin_fails_closed_without_network_or_credentials(): void
    {
        config()->set('services.codebridge_gateway.agent_public_url', '');
        config()->set('services.codebridge_gateway.url', 'http://127.0.0.1:18787');
        Http::fake();

        $this->artisan('codebridge:agent-origin-doctor')
            ->expectsOutput('CODEBRIDGE_PUBLIC_AGENT_ORIGIN=FAIL')
            ->expectsOutput('CODEBRIDGE_PUBLIC_AGENT_AUTH_CHALLENGE=FAIL')
            ->expectsOutput('CODEBRIDGE_PAIRING_CONFIG=BLOCKED')
            ->assertExitCode(1);

        Http::assertNothingSent();
    }

    public function test_exact_public_origin_and_unauthenticated_401_are_preflight_only(): void
    {
        config()->set('services.codebridge_gateway.agent_public_url', 'https://kmjtechno.com/');
        config()->set('services.codebridge_gateway.url', 'http://127.0.0.1:18787');
        Http::fake([
            'https://kmjtechno.com/agent/health' => Http::response(
                ['error' => 'UNAUTHORIZED'], 401
            ),
        ]);

        $this->artisan('codebridge:agent-origin-doctor')
            ->expectsOutput('CODEBRIDGE_PUBLIC_AGENT_ORIGIN=PASS')
            ->expectsOutput('CODEBRIDGE_PRIVATE_MCP_UPSTREAM=CONFIGURED')
            ->expectsOutput('CODEBRIDGE_PUBLIC_AGENT_AUTH_CHALLENGE=PASS')
            ->expectsOutput('CODEBRIDGE_PAIRING_CONFIG=PREFLIGHT_PASS_NOT_DEVICE_READY')
            ->expectsOutput('CODEBRIDGE_DEVICE_READY=NOT_ATTESTED_BY_THIS_COMMAND')
            ->assertExitCode(0);

        Http::assertSentCount(1);
        Http::assertSent(fn (Request $r): bool => $r->method() === 'POST'
            && $r->url() === 'https://kmjtechno.com/agent/health'
            && ! $r->hasHeader('Authorization'));
    }

    public function test_private_or_foreign_agent_origin_is_rejected_without_network(): void
    {
        Http::fake();

        foreach (['http://127.0.0.1:18787', 'https://example.invalid', 'https://kmjtechno.com.evil.invalid'] as $origin) {
            config()->set('services.codebridge_gateway.agent_public_url', $origin);
            config()->set('services.codebridge_gateway.url', 'http://127.0.0.1:18787');

            $this->artisan('codebridge:agent-origin-doctor')
                ->expectsOutput('CODEBRIDGE_PUBLIC_AGENT_ORIGIN=FAIL')
                ->expectsOutput('CODEBRIDGE_PAIRING_CONFIG=BLOCKED')
                ->assertExitCode(1);
        }
        Http::assertNothingSent();
    }

    public function test_gateway_error_or_redirect_fails_without_calling_it_ready(): void
    {
        config()->set('services.codebridge_gateway.agent_public_url', 'https://kmjtechno.com');
        config()->set('services.codebridge_gateway.url', 'http://127.0.0.1:18787');
        Http::fake(['https://kmjtechno.com/agent/health' => Http::response('', 503)]);

        $this->artisan('codebridge:agent-origin-doctor')
            ->expectsOutput('CODEBRIDGE_PUBLIC_AGENT_AUTH_CHALLENGE=FAIL')
            ->expectsOutput('CODEBRIDGE_PAIRING_CONFIG=BLOCKED')
            ->assertExitCode(1);
    }
}
