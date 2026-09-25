<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicTrustCenterTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_trust_center_is_public_and_rendered_by_the_native_platform(): void
    {
        $this->get('/trust')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('trust'));
    }
}
