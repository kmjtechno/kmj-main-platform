<?php

declare(strict_types=1);

namespace Tests\Feature\Mail;

use App\Models\AiModelEvidence;
use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Str;
use Mockery;
use Tests\TestCase;

final class NativeMailAiTest extends TestCase
{
    use RefreshDatabase;

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Mail AI test owner passkey',
            'credential_id' => 'mail-ai-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }

    private function authenticated(User $user): static
    {
        return $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()]);
    }

    public function test_verified_private_free_model_generates_editable_draft_without_sending_mail(): void
    {
        Mail::fake();
        $owner = $this->owner();
        $tenant = (string) Str::uuid();
        DB::table('organizations')->insert([
            'id' => $tenant, 'name' => 'KMJ AI Mail test',
            'created_at' => now(), 'updated_at' => now(),
        ]);

        $scope = Mockery::mock(ResolvesAiProviderScope::class);
        $scope->shouldReceive('for')->once()->andReturn([
            'organization_id' => $tenant, 'can_manage' => true,
        ]);
        $this->app->instance(ResolvesAiProviderScope::class, $scope);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));

        $provider = AiProvider::query()->create([
            'organization_id' => $tenant,
            'name' => 'Test Verified Private Zero-Cost Model',
            'preset' => 'groq',
            'kind' => 'openai-compatible',
            'base_url' => 'https://api.groq.com/openai/v1',
            'api_key' => 'sk-test-only',
            'key_last4' => 'only',
            'enabled' => true,
            'free_only' => true,
            'health' => 'ok',
            'health_checked_at' => now(),
            'models_cache' => ['private-free-test'],
            'models_checked_at' => now(),
        ]);
        AiModelEvidence::query()->create([
            'organization_id' => $tenant,
            'ai_provider_id' => $provider->id,
            'model_id' => 'private-free-test',
            'price_evidence_url' => 'https://example.com/pricing',
            'price_evidence_note' => 'Verified free model for this test only.',
            'verified_at' => now(),
            'expires_at' => now()->addDays(3),
            'data_handling' => 'no-training-documented',
            'capabilities' => ['chat'],
        ]);
        Http::fake([
            'api.groq.com/*' => Http::response([
                'choices' => [[
                    'message' => [
                        'content' => '{"subject":"Delivery Update","body":"Dear Client,\\nWe have completed the work.\\nRegards, KMJ TECHNO"}',
                    ],
                ]],
            ], 200),
        ]);

        $this->authenticated($owner)->postJson('/operator/mail/ai/generate', [
            'mode' => 'compose',
            'instruction' => 'Client ko politely project completion batao, English mein.',
            'tone' => 'professional',
            'language' => 'english',
            'consent_to_ai_processing' => true,
        ])->assertOk()
            ->assertJsonPath('mode', 'compose')
            ->assertJsonPath('subject', 'Delivery Update')
            ->assertJsonPath('needs_review', true);

        Http::assertSentCount(1);
        Mail::assertNothingOutgoing();
        $this->assertDatabaseCount('kmj_mail_messages', 0);
    }

    public function test_guest_unverified_and_unauthorized_user_cannot_use_mail_ai(): void
    {
        $input = ['mode' => 'compose', 'instruction' => 'Write email', 'consent_to_ai_processing' => true];
        $this->postJson('/operator/mail/ai/generate', $input)->assertUnauthorized();
        $member = User::factory()->create(['email_verified_at' => now()]);
        $this->authenticated($member)->postJson('/operator/mail/ai/generate', $input)->assertForbidden();
        $this->authenticated($member)->postJson('/team/mail/ai/generate', $input)->assertForbidden();
    }

    public function test_explicit_consent_and_bounded_input_required_before_any_ai_routing(): void
    {
        $owner = $this->owner();
        $this->authenticated($owner)->postJson('/operator/mail/ai/generate', [
            'mode' => 'compose', 'instruction' => 'Send a proposal to client',
        ])->assertUnprocessable()->assertJsonValidationErrors('consent_to_ai_processing');

        $this->authenticated($owner)->postJson('/operator/mail/ai/generate', [
            'mode' => 'compose', 'instruction' => str_repeat('a', 2001),
            'consent_to_ai_processing' => true,
        ])->assertUnprocessable()->assertJsonValidationErrors('instruction');

        $this->authenticated($owner)->postJson('/operator/mail/ai/generate', [
            'mode' => 'compose', 'instruction' => 'hello',
            'tone' => 'unsafe', 'consent_to_ai_processing' => true,
        ])->assertUnprocessable()->assertJsonValidationErrors('tone');
    }

    public function test_no_entitled_private_free_route_returns_error_without_sending_mail(): void
    {
        Mail::fake();
        $owner = $this->owner();
        $tenant = (string) Str::uuid();
        $scope = Mockery::mock(ResolvesAiProviderScope::class);
        $scope->shouldReceive('for')->once()->andReturn([
            'organization_id' => $tenant, 'can_manage' => true,
        ]);
        $this->app->instance(ResolvesAiProviderScope::class, $scope);

        $this->authenticated($owner)->postJson('/operator/mail/ai/generate', [
            'mode' => 'compose',
            'instruction' => 'Please politely confirm the project delivery in English.',
            'tone' => 'professional',
            'language' => 'english',
            'consent_to_ai_processing' => true,
        ])->assertStatus(503)->assertJsonPath('error', 'NO_PRIVATE_AI_ROUTE_AVAILABLE');

        $this->assertDatabaseCount('kmj_mail_messages', 0);
        Mail::assertNothingOutgoing();
    }

    public function test_mail_ai_cannot_read_another_users_private_message_even_with_consent(): void
    {
        Mail::fake();
        $owner = $this->owner();
        $staff = User::factory()->create(['email_verified_at' => now()]);
        $this->authenticated($owner)->post('/operator/mail/staff', [
            'target_user_id' => $staff->id,
        ])->assertRedirect();

        DB::table('kmj_mail_messages')->insert([
            'mailbox_user_id' => $owner->id,
            'sender_user_id' => $owner->id,
            'recipient_user_id' => $staff->id,
            'thread_id' => (string) Str::uuid(),
            'folder' => 'sent',
            'subject' => 'Private owner message',
            'body' => 'Do not disclose this text to another mailbox.',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $foreign = (int) DB::table('kmj_mail_messages')->where('mailbox_user_id', $owner->id)->value('id');

        $this->authenticated($staff)->postJson('/team/mail/ai/generate', [
            'mode' => 'explain', 'message_id' => $foreign,
            'consent_to_ai_processing' => true,
        ])->assertNotFound();
        Mail::assertNothingOutgoing();
    }
}
