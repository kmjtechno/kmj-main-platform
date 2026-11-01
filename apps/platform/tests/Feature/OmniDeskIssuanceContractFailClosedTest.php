<?php

declare(strict_types=1);

namespace Tests\Feature;

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
                \Illuminate\Http\Request::create('/'.$uri, 'POST')
            );
            self::assertSame($uri, $route->uri());
            self::assertContains('POST', $route->methods());
        }
    }

    public function test_nonmanager_cannot_use_protected_issuance_paths(): void
    {
        app()->instance(
            \App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer::class,
            new class implements \App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer
            {
                public function authorize(\Illuminate\Http\Request $request): \App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal
                {
                    return new \App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal('test-actor', 'test-org', false);
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
            \App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer::class,
            new class implements \App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer
            {
                public function authorize(\Illuminate\Http\Request $request): \App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal
                {
                    return new \App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal('test-manager', 'test-org', true);
                }
            }
        );

        foreach (['activations', 'leases/renew'] as $suffix) {
            $this->postJson('/api/v1/licensing/omnidesk/'.$suffix, [])
                ->assertStatus(503)
                ->assertJsonPath('error', 'ISSUANCE_NOT_CONFIGURED');
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
            $response->assertHeader('Cache-Control', 'no-store');
        }
    }
}
