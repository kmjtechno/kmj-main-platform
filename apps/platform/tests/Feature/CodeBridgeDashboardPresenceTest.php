<?php

namespace Tests\Feature;

use App\Services\CodeBridge\DashboardPresence;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class CodeBridgeDashboardPresenceTest extends TestCase
{
    private const URL = 'http://127.0.0.1:18787/internal/dashboard/presence';

    protected function setUp(): void
    {
        parent::setUp();
        config([
            'codebridge.enabled' => true,
            'codebridge.dashboard_presence_enabled' => true,
            'codebridge.dashboard_presence_token' => str_repeat('x', 48),
            'services.codebridge_gateway.url' => 'http://127.0.0.1:18787',
        ]);
        Http::preventStrayRequests();
    }

    private function devices(): array
    {
        return [
            ['id' => 'desk', 'pairing_state' => 'redeemed', 'projects' => [['id' => 'project']], 'pending_projects' => [['id' => 'pending']]],
            ['id' => 'unredeemed', 'pairing_state' => 'approved_unredeemed', 'projects' => [['id' => 'project']]],
        ];
    }

    private function receipt(): array
    {
        $timestamp = gmdate('Y-m-d\\TH:i:s', time()).'.000Z';

        return [
            'tenant' => 'tenant-a',
            'observedAt' => $timestamp,
            'entries' => [
                ['device' => 'desk', 'project' => 'project', 'status' => 'READY', 'lastSeenAt' => $timestamp],
            ],
        ];
    }

    public function test_only_redeemed_grants_are_sent_and_credentials_never_returned(): void
    {
        Http::fake([self::URL => Http::response($this->receipt())]);
        $snapshot = app(DashboardPresence::class)->snapshot('tenant-a', $this->devices());
        self::assertSame('READY', $snapshot['entries'][0]['status']);
        self::assertArrayNotHasKey('tenant', $snapshot);
        self::assertStringNotContainsString(str_repeat('x', 48), json_encode($snapshot));
        Http::assertSent(fn (Request $request): bool => $request->url() === self::URL
            && $request->hasHeader('Authorization', 'Bearer '.str_repeat('x', 48))
            && $request->data() === [
                'tenant' => 'tenant-a',
                'grants' => [['device' => 'desk', 'project' => 'project']],
            ]);
    }

    public function test_disabled_or_non_loopback_endpoint_never_sends_a_request(): void
    {
        Http::fake();
        config(['codebridge.dashboard_presence_enabled' => false]);
        self::assertNull(app(DashboardPresence::class)->snapshot('tenant-a', $this->devices()));
        config(['codebridge.dashboard_presence_enabled' => true]);
        foreach (['https://gateway.example', 'http://127.0.0.1:18787@foreign.example', 'http://127.0.0.1:18787/path'] as $origin) {
            config(['services.codebridge_gateway.url' => $origin]);
            self::assertNull(app(DashboardPresence::class)->snapshot('tenant-a', $this->devices()));
        }
        Http::assertNothingSent();
    }

    public function test_stale_or_wrong_scope_responses_never_claim_ready(): void
    {
        $wrongTenant = $this->receipt();
        $wrongTenant['tenant'] = 'tenant-b';
        $wrongProject = $this->receipt();
        $wrongProject['entries'][0]['project'] = 'pending';
        $stale = $this->receipt();
        $stale['observedAt'] = gmdate('Y-m-d\\TH:i:s', time() - 60).'.000Z';
        $oldHeartbeat = $this->receipt();
        $oldHeartbeat['entries'][0]['lastSeenAt'] = gmdate('Y-m-d\\TH:i:s', time() - 60).'.000Z';
        Http::fake([self::URL => Http::sequence()
            ->push($wrongTenant)
            ->push($wrongProject)
            ->push($stale)
            ->push($oldHeartbeat)
            ->push([], 503)]);
        $service = app(DashboardPresence::class);
        for ($i = 0; $i < 3; $i++) {
            self::assertNull($service->snapshot('tenant-a', $this->devices()));
        }
        $snapshot = $service->snapshot('tenant-a', $this->devices());
        self::assertSame('UNKNOWN', $snapshot['entries'][0]['status']);
        self::assertNull($snapshot['entries'][0]['lastSeenAt']);
        self::assertNull($service->snapshot('tenant-a', $this->devices()));
    }
}
