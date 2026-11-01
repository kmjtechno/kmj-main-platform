<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer;
use App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Tests\TestCase;

final class OmniDeskIssuanceContractFailClosedTest extends TestCase
{
    public function test_activation_and_renewal_contract_routes_are_registered(): void
    {
        foreach ([
            'api/v1/licensing/omnidesk/activations',
            'api/v1/licensing/omnidesk/leases/renew',
        ] as $uri) {
            $route = Route::getRoutes()->match(
                Request::create('/'.$uri, 'POST')
            );
            self::assertSame($uri, $route->uri());
            self::assertContains('POST', $route->methods());
        }
    }

    public function test_nonmanager_cannot_use_protected_issuance_paths(): void
    {
        app()->instance(
            OmniDeskApiAuthorizer::class,
            new class implements OmniDeskApiAuthorizer
            {
                public function authorize(Request $request): OmniDeskApiPrincipal
                {
                    return new OmniDeskApiPrincipal('test-actor', 'test-org', false);
                }
            }
        );

        foreach (['activations', 'leases/renew'] as $suffix) {
            $this->postJson('/api/v1/licensing/omnidesk/'.$suffix, [])
                ->assertStatus(403)
                ->assertJsonPath('error', 'FORBIDDEN');
        }
    }

    public function test_manager_receives_explicit_unavailable_without_signer(): void
    {
        app()->instance(
            OmniDeskApiAuthorizer::class,
            new class implements OmniDeskApiAuthorizer
            {
                public function authorize(Request $request): OmniDeskApiPrincipal
                {
                    return new OmniDeskApiPrincipal('test-manager', 'test-org', true);
                }
            }
        );

        foreach (['activations', 'leases/renew'] as $suffix) {
            $this->postJson('/api/v1/licensing/omnidesk/'.$suffix, [])
                ->assertStatus(503)
                ->assertJsonPath('error', 'ISSUANCE_NOT_CONFIGURED');
        }
    }

    public function test_unauthenticated_authorizer_failure_is_401_and_not_cached(): void
    {
        app()->instance(
            OmniDeskApiAuthorizer::class,
            new class implements OmniDeskApiAuthorizer
            {
                public function authorize(Request $request): OmniDeskApiPrincipal
                {
                    throw new \DomainException('OMNIDESK_UNAUTHENTICATED');
                }
            }
        );

        foreach (['activations', 'leases/renew'] as $suffix) {
            $response = $this->postJson('/api/v1/licensing/omnidesk/'.$suffix, []);
            $response->assertStatus(401)
                ->assertJsonPath('error', 'UNAUTHENTICATED');
            self::assertStringContainsString(
                'no-store',
                $response->headers->get('Cache-Control', '')
            );
        }
    }

    public function test_oversized_body_is_rejected_without_signer_or_side_effects(): void
    {
        app()->instance(
            OmniDeskApiAuthorizer::class,
            new class implements OmniDeskApiAuthorizer
            {
                public function authorize(Request $request): OmniDeskApiPrincipal
                {
                    return new OmniDeskApiPrincipal('test-manager', 'test-org', true);
                }
            }
        );

        foreach (['activations', 'leases/renew'] as $suffix) {
            $response = $this->postJson('/api/v1/licensing/omnidesk/'.$suffix, [
                'unexpected' => str_repeat('x', 4096),
            ]);
            $response->assertStatus(413)
                ->assertJsonPath('error', 'INVALID_REQUEST');
            self::assertStringContainsString(
                'no-store',
                $response->headers->get('Cache-Control', '')
            );
        }
    }

    public function test_issuance_is_unavailable_without_authorized_signer_integration(): void
    {
        foreach ([
            '/api/v1/licensing/omnidesk/activations',
            '/api/v1/licensing/omnidesk/leases/renew',
        ] as $uri) {
            $response = $this->postJson($uri, []);
            $response->assertStatus(503);
            $response->assertJsonPath('error', 'SERVER_UNAVAILABLE');
            $response->assertHeader('Cache-Control', 'no-store, private');
        }
    }
}
