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
        self::assertStringContainsString(
            'no-store',
            (string) $response->headers->get('Cache-Control'),
        );
    }

    public function test_release_attestation_accepts_only_root_owned_single_link_read_only_exact_sha(): void
    {
        $method = new \ReflectionMethod(StagingDeploymentEvidence::class, 'parseRootAttestation');
        $sha = str_repeat('a', 40);
        $valid = ['uid' => 0, 'nlink' => 1, 'mode' => 0100644, 'size' => 41];

        self::assertSame($sha, $method->invoke(null, $sha."\\n", $valid));
        self::assertSame($sha, $method->invoke(null, $sha, array_replace($valid, ['size' => 40])));

        foreach ([
            ['uid' => 1001],
            ['nlink' => 2],
            ['mode' => 0100666],
            ['size' => 42],
            ['size' => 39],
        ] as $invalid) {
            self::assertNull($method->invoke(null, $sha."\\n", array_replace($valid, $invalid)));
        }

        self::assertNull($method->invoke(null, str_repeat('z', 40)."\\n", $valid));
        self::assertNull($method->invoke(null, $sha."\\nEXTRA", $valid));
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
