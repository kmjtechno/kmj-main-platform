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
use Tests\TestCase;

final class JmapOwnerInboxEndpointTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_and_unconfirmed_user_cannot_access_endpoint(): void
    {
        $url = route('kmj-mail.jmap-inbox');
        $this->postJson($url, ['position' => 0])->assertUnauthorized();

        $owner = $this->owner();
        $this->actingAs($owner)->postJson($url, ['position' => 0])->assertStatus(423);
    }

    public function test_disabled_and_unbound_owner_never_contact_engine(): void
    {
        $owner = $this->owner();
        $other = $this->owner();
        $history = [];
        $this->installPilot($history);
        config()->set('kmj-mail-engine.pilot_owner_id', $owner->id);
        config()->set('kmj-mail-engine.pilot_enabled', false);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(route('kmj-mail.jmap-inbox'), ['position' => 0])
            ->assertForbidden()->assertJsonPath('status', 'unavailable');

        config()->set('kmj-mail-engine.pilot_enabled', true);
        $this->actingAs($other)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(route('kmj-mail.jmap-inbox'), ['position' => 0])
            ->assertForbidden();
        self::assertSame([], $history);
    }

    public function test_browser_cannot_supply_account_or_message_ids(): void
    {
        $owner = $this->owner();
        $history = [];
        $this->installPilot($history);
        config()->set('kmj-mail-engine.pilot_enabled', true);
        config()->set('kmj-mail-engine.pilot_owner_id', $owner->id);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(route('kmj-mail.jmap-inbox'), ['position' => 0, 'accountId' => 'foreign'])
            ->assertUnprocessable()->assertJsonPath('status', 'invalid_position');
        self::assertSame([], $history);
    }

    public function test_explicit_null_and_non_integer_positions_are_rejected_without_engine_access(): void
    {
        $owner = $this->owner();
        $history = [];
        $this->installPilot($history);
        $this->configure($owner);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()]);

        foreach ([null, '0', true, -1, 40001, [], 0.5] as $position) {
            $this->postJson(route('kmj-mail.jmap-inbox'), ['position' => $position])
                ->assertUnprocessable()->assertJsonPath('status', 'invalid_position');
        }

        self::assertSame([], $history);
    }

    public function test_confirmed_bound_owner_receives_only_summary_with_private_cache_policy(): void
    {
        $owner = $this->owner();
        $history = [];
        $this->configure($owner);
        $this->installPilot($history, [
            $this->session(),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Mailbox/get",{"accountId":"a1","state":"s1","list":[{"id":"inbox1","name":"Inbox","parentId":null,"role":"inbox","sortOrder":0,"totalEmails":1,"unreadEmails":1}],"notFound":[]},"mailboxes"]]}'),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Email/query",{"accountId":"a1","queryState":"q1","position":0,"ids":["e1"],"total":1},"inbox-query"]]}'),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Email/get",{"accountId":"a1","state":"s1","list":[{"id":"e1","threadId":"t1","receivedAt":"2026-11-25T12:00:00Z","subject":"Synthetic message","from":[{"name":"Sender","email":"sender@example.test"}],"keywords":{},"hasAttachment":false,"bodyValues":{"hidden":{"value":"not exposed"}}}],"notFound":[]},"inbox-metadata"]]}'),
        ]);

        $response = $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(route('kmj-mail.jmap-inbox'), [])
            ->assertOk()->assertJsonPath('status', 'available')
            ->assertJsonPath('inbox.messages.0.id', 'e1')
            ->assertJsonPath('inbox.messages.0.subject', 'Synthetic message')
            ->assertJsonPath('inbox.total', 1)
            ->assertJsonPath('inbox.position', 0)
            ->assertJsonMissingPath('inbox.messages.0.bodyValues')
            ->assertDontSee('synthetic-token');

        self::assertStringContainsString('no-store', (string) $response->headers->get('Cache-Control'));
        self::assertStringContainsString('private', (string) $response->headers->get('Cache-Control'));
        self::assertCount(4, $history);
    }

    public function test_engine_failure_returns_generic_uncached_error(): void
    {
        $owner = $this->owner();
        $history = [];
        $this->configure($owner);
        $this->installPilot($history, [
            new Response(502, ['Content-Type' => 'application/json'], '{"error":"synthetic-private-provider-detail"}'),
        ]);

        $response = $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson(route('kmj-mail.jmap-inbox'), ['position' => 0])
            ->assertStatus(503)->assertExactJson(['status' => 'unavailable'])
            ->assertDontSee('synthetic-private-provider-detail');

        self::assertStringContainsString('no-store', (string) $response->headers->get('Cache-Control'));
        self::assertCount(1, $history);
    }

    private function configure(User $owner): void
    {
        config()->set('kmj-mail-engine.pilot_enabled', true);
        config()->set('kmj-mail-engine.pilot_owner_id', $owner->id);
        config()->set('kmj-mail-engine.pilot_username', 'pilot@kmjtechno.com');
        config()->set('kmj-mail-engine.pilot_access_token', 'synthetic-token');
    }

    private function session(): Response
    {
        $mail = 'urn:ietf:params:jmap:mail';

        return new Response(200, ['Content-Type' => 'application/json'], json_encode([
            'username' => 'pilot@kmjtechno.com',
            'apiUrl' => 'https://mail.kmjtechno.com/jmap/',
            'capabilities' => ['urn:ietf:params:jmap:core' => new \stdClass, $mail => new \stdClass],
            'primaryAccounts' => [$mail => 'a1'],
            'accounts' => ['a1' => ['isPersonal' => true, 'accountCapabilities' => [$mail => new \stdClass]]],
        ], JSON_THROW_ON_ERROR));
    }

    /**
     * @param  array<int, mixed>  $history
     * @param  list<Response>  $responses
     */
    private function installPilot(array &$history, array $responses = []): void
    {
        $stack = HandlerStack::create(new MockHandler($responses));
        $stack->push(Middleware::history($history));
        $this->app->instance(JmapOwnerPilot::class, new JmapOwnerPilot(
            new PlatformOwnerAccess,
            new JmapReadOnlyTransport(new Client(['handler' => $stack])),
        ));
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
            'name' => 'Synthetic KMJ Inbox owner',
            'credential_id' => 'kmj-jmap-inbox-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
