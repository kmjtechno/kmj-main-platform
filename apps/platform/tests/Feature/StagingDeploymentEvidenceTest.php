<?php

namespace Tests\Feature;

use App\Http\Middleware\StagingDeploymentEvidence;
use Illuminate\Filesystem\Filesystem;
use Illuminate\Http\Request;
use Tests\TestCase;

final class StagingDeploymentEvidenceTest extends TestCase
{
    private string $originalBasePath;

    private string $fixtureRoot;

    protected function setUp(): void
    {
        parent::setUp();

        $this->originalBasePath = base_path();
        $this->fixtureRoot = sys_get_temp_dir().'/kmj-staging-evidence-'.bin2hex(random_bytes(8));
        $files = new Filesystem;
        $files->makeDirectory($this->fixtureRoot.'/.git', 0700, true);
        $files->makeDirectory($this->fixtureRoot.'/apps/platform', 0700, true);
        $files->put($this->fixtureRoot.'/.git/HEAD', str_repeat('a', 40)."\n");
        $this->app->setBasePath($this->fixtureRoot.'/apps/platform');
    }

    protected function tearDown(): void
    {
        try {
            $this->app->setBasePath($this->originalBasePath);
            (new Filesystem)->deleteDirectory($this->fixtureRoot);
        } finally {
            parent::tearDown();
        }
    }

    public function test_staging_host_receives_exact_repository_sha_header(): void
    {
        $request = Request::create('https://staging.kmjtechno.com/', 'GET');

        $response = app(StagingDeploymentEvidence::class)->handle(
            $request,
            static fn () => response('ok'),
        );

        self::assertSame(
            str_repeat('a', 40),
            (string) $response->headers->get('X-KMJ-Deploy-SHA'),
        );
        self::assertStringContainsString(
            'no-store',
            (string) $response->headers->get('Cache-Control'),
        );
    }

    public function test_staging_host_does_not_invent_sha_when_git_metadata_is_missing(): void
    {
        (new Filesystem)->deleteDirectory($this->fixtureRoot.'/.git');
        $request = Request::create('https://staging.kmjtechno.com/', 'GET');

        $response = app(StagingDeploymentEvidence::class)->handle(
            $request,
            static fn () => response('ok'),
        );

        self::assertFalse($response->headers->has('X-KMJ-Deploy-SHA'));
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
