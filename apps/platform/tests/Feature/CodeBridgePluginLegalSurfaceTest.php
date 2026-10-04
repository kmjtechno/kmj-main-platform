<?php

namespace Tests\Feature;

use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class CodeBridgePluginLegalSurfaceTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_codebridge_plugin_legal_and_support_pages_are_public(): void
    {
        $pages = [
            '/products/kmj-codebridge/terms' => 'products/codebridge/terms',
            '/products/kmj-codebridge/privacy' => 'products/codebridge/privacy',
            '/products/kmj-codebridge/support' => 'products/codebridge/support',
        ];

        foreach ($pages as $path => $component) {
            $this->get($path)
                ->assertOk()
                ->assertInertia(fn (Assert $page) => $page->component($component));
        }
    }
}
