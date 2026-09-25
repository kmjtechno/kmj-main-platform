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

    public function test_public_pages_share_configured_canonical_origin_and_fail_closed_indexing(): void
    {
        config()->set('app.url', 'https://kmjtechno.example/');
        config()->set('app.public_indexing', false);

        $this->get('/products')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('products/index')
                ->where('publicSite.base_url', 'https://kmjtechno.example')
                ->where('publicSite.indexable', false));
    }

    public function test_public_indexing_can_be_explicitly_enabled_for_production(): void
    {
        config()->set('app.public_indexing', true);

        $this->get('/company')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('company')
                ->where('publicSite.indexable', true));
    }

    public function test_private_surfaces_remain_noindex_when_public_indexing_is_enabled(): void
    {
        config()->set('app.public_indexing', true);

        $this->get('/login')
            ->assertOk()
            ->assertSee(
                '<meta name="robots" content="noindex,nofollow">',
                false,
            );
    }

    public function test_non_indexable_environment_emits_server_rendered_robots_policy(): void
    {
        config()->set('app.public_indexing', false);

        $this->get('/company')
            ->assertOk()
            ->assertSee(
                '<meta name="robots" content="noindex,nofollow">',
                false,
            );
    }
}
