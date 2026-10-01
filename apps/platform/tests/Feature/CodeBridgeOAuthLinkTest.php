<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CodeBridgeOAuthLinkTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_is_redirected_to_login(): void
    {
        $response = $this->get('/codebridge-oauth-link/abcdefghijklmnop');

        $response->assertRedirect(route('login'));
    }

    public function test_authenticated_user_sees_explicit_codebridge_permissions(): void
    {
        $user = User::factory()->create();

        $response = $this->actingAs($user)->get('/codebridge-oauth-link/abcdefghijklmnop');

        $response->assertOk()
            ->assertSee('Connect KMJ CodeBridge')
            ->assertSee('codebridge:read')
            ->assertSee('codebridge:write')
            ->assertSee('codebridge:execute')
            ->assertSee($user->email);
    }

    public function test_approval_returns_short_lived_signed_assertion_without_password(): void
    {
        config()->set('services.codebridge_oauth.link_secret', str_repeat('a', 64));
        $user = User::factory()->create();

        $response = $this->actingAs($user)->post('/codebridge-oauth-link/abcdefghijklmnop');

        $response->assertRedirect();
        $location = $response->headers->get('Location');
        $this->assertIsString($location);
        $parts = parse_url($location);
        $this->assertIsArray($parts);
        $this->assertSame('/codebridge-oauth/interaction/abcdefghijklmnop/complete', $parts['path'] ?? null);
        parse_str((string) ($parts['query'] ?? ''), $query);
        $this->assertIsString($query['assertion'] ?? null);
        $this->assertNotSame('', $query['assertion'] ?? '');
        $this->assertStringNotContainsString((string) $user->password, $location);
        $this->assertStringNotContainsString('password', $location);
    }

    public function test_invalid_interaction_uid_is_rejected(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)->get('/codebridge-oauth-link/bad')->assertNotFound();
    }
}
