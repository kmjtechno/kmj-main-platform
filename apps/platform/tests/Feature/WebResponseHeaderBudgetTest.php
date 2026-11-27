<?php

namespace Tests\Feature;

use Illuminate\Contracts\Http\Kernel;
use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
use Illuminate\Routing\Router;
use Tests\TestCase;

final class WebResponseHeaderBudgetTest extends TestCase
{
    /**
     * A Link header with one entry per built asset grows with the frontend and
     * can overflow the web server header buffer and turn a page into a 502.
     */
    public function test_web_pages_do_not_send_a_preload_link_header(): void
    {
        // The configured groups exist once the HTTP kernel has been resolved.
        $this->app->make(Kernel::class);
        $web = $this->app->make(Router::class)->getMiddlewareGroups()['web'];

        $this->assertNotEmpty($web);
        $this->assertNotContains(AddLinkHeadersForPreloadedAssets::class, $web);
    }
}
