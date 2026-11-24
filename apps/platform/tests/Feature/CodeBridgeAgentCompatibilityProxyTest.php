<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class CodeBridgeAgentCompatibilityProxyTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        config([
            'codebridge_oauth.enabled' => true,
            'codebridge_oauth.issuer' => 'https://kmj.example',
            'codebridge_oauth.resource' => 'https://kmj.example/mcp',
            'codebridge_oauth.signing_key' => base64_encode(str_repeat("\x07", SODIUM_CRYPTO_SIGN_SEEDBYTES)),
            'codebridge_oauth.kid' => 'test-kid',
            'services.codebridge_gateway.url' => 'https://gateway.example',
        ]);
    }

    public function test_legacy_agent_health_is_forwarded_to_authoritative_gateway(): void
    {
        Http::fake([
            'https://gateway.example/agent/health' => Http::response(
                ['ok' => true],
                200,
                ['Content-Type' => 'application/json'],
            ),
        ]);

        $this->withHeader('Authorization', 'Bearer device-token')
            ->postJson('/agent/health', [])
            ->assertOk()
            ->assertJson(['ok' => true])
            ->assertHeader('Cache-Control', 'no-store, private');

        Http::assertSent(fn (Request $request): bool => $request->url() === 'https://gateway.example/agent/health'
            && $request->method() === 'POST'
            && $request->hasHeader('Authorization', 'Bearer device-token'));
    }

    public function test_legacy_agent_proxy_is_fixed_to_known_post_operations(): void
    {
        $this->postJson('/agent/debug', [])->assertNotFound();
        $this->get('/agent/health')->assertStatus(405);
    }

    public function test_legacy_agent_proxy_fails_closed_when_gateway_is_unavailable(): void
    {
        Http::fake([
            '*' => function (): never {
                throw new \RuntimeException('offline');
            },
        ]);

        $this->postJson('/agent/health', [])
            ->assertStatus(503)
            ->assertJson(['error' => 'CODEBRIDGE_GATEWAY_UNAVAILABLE']);
    }

    public function test_empty_upstream_never_forwards_mcp_or_agent_credentials(): void
    {
        $source = file_get_contents(config_path('services.php'));
        self::assertIsString($source);
        self::assertStringNotContainsString('onrender.com', $source);

        config()->set('services.codebridge_gateway.url', '');
        Http::fake();

        $this->withHeader('Authorization', 'Bearer should-never-be-forwarded')
            ->postJson('/agent/health', [])
            ->assertStatus(503);

        $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 1,
            'method' => 'tools/list',
            'params' => [],
        ])->assertStatus(503);

        Http::assertNothingSent();
    }
    public function test_negotiated_status_progress_preserves_upstream_sse_frames(): void
    {
        $frames = "event: message\ndata: {\"jsonrpc\":\"2.0\",\"method\":\"notifications/progress\",\"params\":{\"progressToken\":0,\"progress\":1}}\n\nevent: message\ndata: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"content\":[]}}\n\n";
        Http::fake([
            'https://gateway.example/mcp' => Http::response($frames, 200, ['Content-Type' => 'text/event-stream; charset=utf-8']),
        ]);

        $response = $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 1,
            'method' => 'tools/call',
            'params' => [
                'name' => 'render_codebridge_status',
                'arguments' => ['device' => 'd1', 'project' => 'p1'],
                '_meta' => ['progressToken' => 0],
            ],
        ], ['Authorization' => 'Bearer test-token', 'Accept' => 'application/json, text/event-stream']);

        $response->assertOk()->assertHeader('Content-Type', 'text/event-stream')->assertHeader('X-Accel-Buffering', 'no');
        self::assertSame($frames, $response->streamedContent());
        Http::assertSent(fn (Request $request): bool => $request->hasHeader('Authorization', 'Bearer test-token')
            && $request->hasHeader('Accept', 'application/json, text/event-stream'));
    }

    public function test_status_progress_keeps_upstream_json_denials_intact(): void
    {
        Http::fake([
            'https://gateway.example/mcp' => Http::response(['error' => 'UNAUTHORIZED'], 401, [
                'Content-Type' => 'application/json',
                'WWW-Authenticate' => 'Bearer error="invalid_token"',
            ]),
        ]);

        $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 1,
            'method' => 'tools/call',
            'params' => [
                'name' => 'render_codebridge_status',
                '_meta' => ['progressToken' => 'test'],
            ],
        ], ['Authorization' => 'Bearer test-token', 'Accept' => 'application/json, text/event-stream'])
            ->assertUnauthorized()
            ->assertHeader('WWW-Authenticate', 'Bearer error="invalid_token"')
            ->assertJson(['error' => 'UNAUTHORIZED']);
    }

}
