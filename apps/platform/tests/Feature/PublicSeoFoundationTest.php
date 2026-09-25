<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicSeoFoundationTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_public_pages_share_configured_canonical_origin(): void
    {
        config()->set('app.url', 'https://kmjtechno.example/');

        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->where('publicSite.base_url', 'https://kmjtechno.example'));
    }
}
