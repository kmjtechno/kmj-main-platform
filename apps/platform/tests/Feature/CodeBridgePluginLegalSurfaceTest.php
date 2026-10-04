<?php

use Inertia\Testing\AssertableInertia as Assert;

it('serves product-specific CodeBridge plugin legal and support pages', function (): void {
    $this->get('/products/kmj-codebridge/terms')
        ->assertOk()
        ->assertInertia(fn (Assert $page): Assert => $page->component('products/codebridge/terms'));

    $this->get('/products/kmj-codebridge/privacy')
        ->assertOk()
        ->assertInertia(fn (Assert $page): Assert => $page->component('products/codebridge/privacy'));

    $this->get('/products/kmj-codebridge/support')
        ->assertOk()
        ->assertInertia(fn (Assert $page): Assert => $page->component('products/codebridge/support'));
});
