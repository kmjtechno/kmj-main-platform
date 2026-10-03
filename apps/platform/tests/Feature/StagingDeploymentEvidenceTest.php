<?php

namespace Tests\Feature;

use App\Http\Middleware\StagingDeploymentEvidence;
use Illuminate\Http\Request;
use Tests\TestCase;

final class StagingDeploymentEvidenceTest extends TestCase
{
    public function test_staging_host_receives_exact_repository_sha_header(): void
    {
        $request = Request::create('https://staging.kmjtechno.com/', 'GET');

        $response = app(StagingDeploymentEvidence::class)->handle(
            $request,
            static fn () => response('ok'),
        );

        self::assertMatchesRegularExpression(
            '/^[0-9a-f]{40}$/',
            (string) $response->headers->get('X-KMJ-Deploy-SHA'),
        );
        self::assertSame('no-store, private', $response->headers->get('Cache-Control'));
    }

    public function test_production_host_does_not_receive_deployment_sha_header(): void
    {
        $request = Request::create('https://kmjtechno.com/', 'GET');

        $response = app(StagingDeploymentEvidence::class)->handle(
            $request,
            static fn () => response('ok'),
        );

        self::assertFalse($response->headers->has('X-KMJ-Deploy-SHA'));
    }
}
