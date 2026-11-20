<?php

namespace Tests\Feature;

use App\Http\Middleware\SecurityHeaders;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Tests\TestCase;

final class SecurityHeadersTest extends TestCase
{
    private function through(Request $request, ?callable $inner = null): \Symfony\Component\HttpFoundation\Response
    {
        return (new SecurityHeaders)->handle($request, $inner ?? fn () => new Response('ok'));
    }

    public function test_adds_baseline_headers_without_hsts_on_plain_http(): void
    {
        $response = $this->through(Request::create('http://kmjtechno.test/'));

        $this->assertSame('nosniff', $response->headers->get('X-Content-Type-Options'));
        $this->assertSame('strict-origin-when-cross-origin', $response->headers->get('Referrer-Policy'));
        $this->assertSame('SAMEORIGIN', $response->headers->get('X-Frame-Options'));
        $this->assertSame(SecurityHeaders::CSP, $response->headers->get('Content-Security-Policy'));
        $this->assertNull($response->headers->get('Strict-Transport-Security'));
    }

    public function test_adds_hsts_only_over_https_without_subdomains_or_preload(): void
    {
        $response = $this->through(Request::create('https://kmjtechno.test/'));

        $this->assertSame('max-age=15552000', $response->headers->get('Strict-Transport-Security'));
        $this->assertStringNotContainsString('includeSubDomains', SecurityHeaders::HSTS);
        $this->assertStringNotContainsString('preload', SecurityHeaders::HSTS);
    }

    public function test_csp_does_not_restrict_scripts_styles_forms_or_connections(): void
    {
        foreach (['script-src', 'style-src', 'default-src', 'form-action', 'connect-src', 'img-src'] as $directive) {
            $this->assertStringNotContainsString($directive, SecurityHeaders::CSP);
        }
        $this->assertStringContainsString("frame-ancestors 'self'", SecurityHeaders::CSP);
        $this->assertStringContainsString("object-src 'none'", SecurityHeaders::CSP);
    }

    public function test_never_overrides_a_header_the_controller_already_set(): void
    {
        $response = $this->through(Request::create('https://kmjtechno.test/'), function () {
            return new Response('media', 200, [
                'Content-Security-Policy' => "default-src 'none'; sandbox",
                'X-Content-Type-Options' => 'nosniff',
            ]);
        });

        $this->assertSame("default-src 'none'; sandbox", $response->headers->get('Content-Security-Policy'));
    }

    public function test_kill_switch_disables_all_headers(): void
    {
        config(['security-headers.enabled' => false]);

        $response = $this->through(Request::create('https://kmjtechno.test/'));

        $this->assertNull($response->headers->get('X-Content-Type-Options'));
        $this->assertNull($response->headers->get('Content-Security-Policy'));
        $this->assertNull($response->headers->get('Strict-Transport-Security'));
    }

    public function test_is_registered_on_the_web_group_so_real_responses_carry_headers(): void
    {
        $response = $this->get('/');

        $response->assertHeader('X-Content-Type-Options', 'nosniff');
        $response->assertHeader('Content-Security-Policy', SecurityHeaders::CSP);
    }
}
