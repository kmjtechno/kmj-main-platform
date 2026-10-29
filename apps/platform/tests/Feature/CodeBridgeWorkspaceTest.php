<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class CodeBridgeWorkspaceTest extends TestCase
{
    use RefreshDatabase;

    public function test_guests_are_redirected_and_unentitled_users_get_404(): void
    {
        $this->get('/services/kmj-codebridge/workspace')->assertRedirect();

        $stranger = User::factory()->create(['email_verified_at' => now()]);
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([]));
        $this->actingAs($stranger)->get('/services/kmj-codebridge/workspace')->assertNotFound();
    }

    public function test_workspace_reports_only_real_state_and_marks_missing_backends_unavailable(): void
    {
        $org = (string) Str::uuid();
        $other = (string) Str::uuid();
        foreach ([$org, $other] as $id) {
            DB::table('organizations')->insert(['id' => $id, 'name' => 'Org '.$id, 'created_at' => now(), 'updated_at' => now()]);
        }
        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $user->id => ['organization_id' => $org, 'can_manage' => false],
        ]));
        $this->provider($org, 'Mine');
        $this->provider($other, 'Other tenant');

        $this->actingAs($user)->get('/services/kmj-codebridge/workspace')
            ->assertOk()
            ->assertInertia(fn (AssertableInertia $page) => $page
                ->component('services/codebridge-workspace')
                ->where('canManage', false)
                ->has('providers', 1)
                ->where('providers.0.name', 'Mine')
                ->missing('providers.0.api_key')
                ->where('capabilities.chat_executor.available', false)
                ->where('capabilities.conversations.available', true)
                ->where('capabilities.job_events.available', false)
                ->where('devices', []));
    }

    private function provider(string $organizationId, string $name): AiProvider
    {
        $provider = new AiProvider;
        $provider->forceFill([
            'organization_id' => $organizationId,
            'created_by' => User::factory()->create()->id,
            'name' => $name,
            'preset' => 'groq',
            'kind' => 'openai-compatible',
            'base_url' => 'https://api.groq.com/openai/v1',
            'api_key' => 'gsk_test_0123456789abcdef',
            'key_last4' => 'cdef',
            'enabled' => true,
            'free_only' => true,
            'health' => 'unknown',
        ])->save();

        return $provider;
    }
}
