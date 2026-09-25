<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicCorporateSurfaceTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_company_page_is_public_and_native(): void
    {
        $this->get('/company')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('company'));
    }

    public function test_capabilities_page_is_public_and_native(): void
    {
        $this->get('/capabilities')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('capabilities'));
    }
}
