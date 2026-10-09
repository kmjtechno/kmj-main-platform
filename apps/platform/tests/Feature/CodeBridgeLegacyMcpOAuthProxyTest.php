<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class CodeBridgeLegacyMcpOAuthProxyTest extends TestCase
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

    private function legacyDenial(string $scope = 'read', ?string $metadata = null): array
    {
        $metadata ??= 'https://kmj.example/.well-known/oauth-protected-resource';

        return [
            'jsonrpc' => '2.0',
            'id' => 3,
            'result' => [
                'isError' => true,
                'content' => [['type' => 'text', 'text' => '{"error":"UNAUTHORIZED"}']],
                '_meta' => [
                    'mcp/www_authenticate' => [
                        'Bearer resource_metadata="'.$metadata.'", scope="codebridge:'.$scope.'", error="invalid_token"',
                    ],
                ],
            ],
        ];
    }

    public function test_verified_legacy_denial_becomes_http_401_and_starts_client_oauth(): void
    {
        Http::fake([
            'https://gateway.example/mcp' => Http::response($this->legacyDenial(), 200),
        ]);

        $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 3,
            'method' => 'tools/call',
            'params' => ['name' => 'list_devices', 'arguments' => []],
        ])->assertStatus(401)
            ->assertJson(['error' => 'UNAUTHORIZED'])
            ->assertHeader('Cache-Control', 'no-store, private')
            ->assertHeader(
                'WWW-Authenticate',
                'Bearer resource_metadata="https://kmj.example/.well-known/oauth-protected-resource", scope="codebridge:read", error="invalid_token"',
            );

        Http::assertSent(fn (Request $request): bool => $request->url() === 'https://gateway.example/mcp'
            && $request->method() === 'POST');
    }

    public function test_write_challenge_uses_exact_least_privilege_scope(): void
    {
        Http::fake([
            'https://gateway.example/mcp' => Http::response($this->legacyDenial('write'), 200),
        ]);

        $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 3,
            'method' => 'tools/call',
            'params' => ['name' => 'write_file', 'arguments' => []],
        ])->assertStatus(401)
            ->assertHeader(
                'WWW-Authenticate',
                'Bearer resource_metadata="https://kmj.example/.well-known/oauth-protected-resource", scope="codebridge:write", error="invalid_token"',
            );
    }

    public function test_unverified_tool_errors_and_successes_remain_unchanged(): void
    {
        $normalSuccess = [
            'jsonrpc' => '2.0',
            'id' => 3,
            'result' => ['content' => [['type' => 'text', 'text' => '{"devices":[]}']]],
        ];
        $normalError = [
            'jsonrpc' => '2.0',
            'id' => 3,
            'result' => ['isError' => true, 'content' => [['type' => 'text', 'text' => '{"error":"PROJECT_OFFLINE"}']]],
        ];
        $wrongMetadata = $this->legacyDenial('read', 'https://attacker.example/.well-known/oauth-protected-resource');
        $unknownScope = $this->legacyDenial('admin');
        $missingChallenge = $this->legacyDenial();
        unset($missingChallenge['result']['_meta']);
        $unverifiedError = $this->legacyDenial();
        $unverifiedError['result']['content'][0]['text'] = '{"error":"OTHER"}';

        $cases = [
            $normalSuccess,
            $normalError,
            $wrongMetadata,
            $unknownScope,
            $missingChallenge,
            $unverifiedError,
        ];

        Http::fake([
            'https://gateway.example/mcp' => Http::sequence()
                ->push($normalSuccess)
                ->push($normalError)
                ->push($wrongMetadata)
                ->push($unknownScope)
                ->push($missingChallenge)
                ->push($unverifiedError),
        ]);

        foreach ($cases as $case) {
            $response = $this->postJson('/mcp', [
                'jsonrpc' => '2.0',
                'id' => 3,
                'method' => 'tools/call',
                'params' => ['name' => 'list_devices', 'arguments' => []],
            ]);
            $response->assertOk()->assertExactJson($case);
            $this->assertFalse($response->headers->has('WWW-Authenticate'));
        }
    }

    public function test_discovery_and_existing_http_401_are_not_rewritten(): void
    {
        Http::fake([
            'https://gateway.example/mcp' => Http::sequence()
                ->push($this->legacyDenial())
                ->push(['error' => 'UNAUTHORIZED'], 401, [
                    'WWW-Authenticate' => 'Bearer resource_metadata="https://kmj.example/.well-known/oauth-protected-resource"',
                ]),
        ]);

        $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 7,
            'method' => 'tools/list',
            'params' => [],
        ])->assertOk();

        $this->postJson('/mcp', [
            'jsonrpc' => '2.0',
            'id' => 8,
            'method' => 'tools/call',
            'params' => ['name' => 'list_devices', 'arguments' => []],
        ])->assertStatus(401)->assertHeader(
            'WWW-Authenticate',
            'Bearer resource_metadata="https://kmj.example/.well-known/oauth-protected-resource"',
        );
    }
}
