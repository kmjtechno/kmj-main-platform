<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class PublicLegalSurfaceTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_legal_center_and_policies_are_public_native_pages(): void
    {
        $pages = [
            '/legal' => 'legal/index',
            '/terms' => 'legal/terms',
            '/privacy' => 'legal/privacy',
            '/refund-policy' => 'legal/refund-policy',
            '/contact' => 'contact',
            '/acceptable-use' => 'legal/acceptable-use',
            '/cookie-policy' => 'legal/cookie-policy',
        ];

        foreach ($pages as $path => $component) {
            $this->get($path)
                ->assertOk()
                ->assertInertia(fn (Assert $page) => $page->component($component));
        }
    }

    public function test_cancellation_url_permanently_redirects_to_existing_policy(): void
    {
        $this->get('/cancellation-policy')
            ->assertStatus(301)
            ->assertRedirect('/refund-policy');
    }
}
