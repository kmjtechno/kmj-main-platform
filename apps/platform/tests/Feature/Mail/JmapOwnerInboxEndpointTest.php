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

    /** @param  array<int, mixed>  $history */
    private function installPilot(array &$history): void
    {
        $stack = HandlerStack::create(new MockHandler([]));
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
