<?php

declare(strict_types=1);

namespace Tests\Feature\Mail;

use App\Models\User;
use App\Services\Mail\JmapOwnerPilot;
use App\Services\Mail\JmapReadOnlyTransport;
use App\Services\PlatformOwnerAccess;
use GuzzleHttp\Client;
use GuzzleHttp\Handler\MockHandler;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Middleware;
use GuzzleHttp\Psr7\Response;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;
use Tests\TestCase;

final class JmapOwnerPilotTest extends TestCase
{
    use RefreshDatabase;

    public function test_default_off_and_wrong_user_never_make_http_requests(): void
    {
        $owner = $this->owner();
        $other = $this->owner();
        $history = [];
        $pilot = $this->pilot($history);
        config()->set('kmj-mail-engine.pilot_owner_id', $owner->id);
        config()->set('kmj-mail-engine.pilot_enabled', false);
        $this->assertDenied($pilot, $owner);

        config()->set('kmj-mail-engine.pilot_enabled', true);
        $this->assertDenied($pilot, $other);
        self::assertSame([], $history);
    }

    public function test_stale_revoked_owner_is_denied_without_http_requests(): void
    {
        $owner = $this->owner();
        $history = [];
        $pilot = $this->pilot($history);
        $this->configure($owner);
        DB::table('users')->where('id', $owner->id)->update(['is_platform_owner' => false]);

        $this->assertDenied($pilot, $owner);
        self::assertSame([], $history);
    }

    public function test_invalid_principal_or_missing_secret_is_denied(): void
    {
        $owner = $this->owner();
        $history = [];
        $pilot = $this->pilot($history);
        $this->configure($owner);
        config()->set('kmj-mail-engine.pilot_username', 'other@example.test');
        $this->assertDenied($pilot, $owner);
        config()->set('kmj-mail-engine.pilot_username', 'pilot@kmjtechno.com');
        config()->set('kmj-mail-engine.pilot_access_token', '');
        $this->assertDenied($pilot, $owner);
        self::assertSame([], $history);
    }

    public function test_current_bound_owner_can_read_synthetic_mailbox(): void
    {
        $owner = $this->owner();
        $history = [];
        $pilot = $this->pilot($history);
        $this->configure($owner);

        self::assertSame([], $pilot->mailboxes($owner));
        self::assertCount(2, $history);
    }

    private function configure(User $owner): void
    {
        config()->set('kmj-mail-engine.pilot_enabled', true);
        config()->set('kmj-mail-engine.pilot_owner_id', $owner->id);
        config()->set('kmj-mail-engine.pilot_username', 'pilot@kmjtechno.com');
        config()->set('kmj-mail-engine.pilot_access_token', 'synthetic-token');
    }

    private function assertDenied(JmapOwnerPilot $pilot, User $user): void
    {
        try {
            $pilot->mailboxes($user);
            self::fail('Unbound KMJ mail pilot accepted.');
        } catch (RuntimeException $exception) {
            self::assertSame('KMJ mail pilot unavailable.', $exception->getMessage());
        }
    }

    /** @param array<int, mixed> $history */
    private function pilot(array &$history): JmapOwnerPilot
    {
        $mail = 'urn:ietf:params:jmap:mail';
        $session = [
            'username' => 'pilot@kmjtechno.com',
            'apiUrl' => 'https://mail.kmjtechno.com/jmap/',
            'capabilities' => ['urn:ietf:params:jmap:core' => new \stdClass, $mail => new \stdClass],
            'primaryAccounts' => [$mail => 'a1'],
            'accounts' => ['a1' => ['isPersonal' => true, 'accountCapabilities' => [$mail => new \stdClass]]],
        ];
        $stack = HandlerStack::create(new MockHandler([
            new Response(200, ['Content-Type' => 'application/json'], json_encode($session, JSON_THROW_ON_ERROR)),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Mailbox/get",{"accountId":"a1","state":"s1","list":[],"notFound":[]},"mailboxes"]]}'),
        ]));
        $stack->push(Middleware::history($history));

        return new JmapOwnerPilot(new PlatformOwnerAccess, new JmapReadOnlyTransport(new Client(['handler' => $stack])));
    }

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Synthetic KMJ mail pilot owner',
            'credential_id' => 'kmj-jmap-pilot-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
