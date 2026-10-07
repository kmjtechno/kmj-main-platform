<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicResourceSurfaceTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_documentation_is_public_and_native(): void
    {
        $this->get('/docs')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('docs'));
    }

    public function test_insights_are_public_and_native(): void
    {
        $this->get('/insights')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('insights'));
    }

    public function test_support_is_public_and_native(): void
    {
        $this->get('/support')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('support'));
    }

    public function test_resource_surfaces_receive_supported_hindi_locale(): void
    {
        foreach (['/docs', '/insights', '/support'] as $path) {
            $this->get($path.'?lang=hi')
                ->assertOk()
                ->assertCookie('kmj_locale')
                ->assertInertia(fn (Assert $page) => $page
                    ->where('localization.locale', 'hi')
                    ->where('localization.switch_locale', 'en'));
        }
    }
}
