<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Website\WebsiteSettings;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\Storage;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class WebsiteSettingsTest extends TestCase
{
    use RefreshDatabase;

    public function test_only_a_verified_platform_owner_can_change_the_website(): void
    {
        $this->put('/operator/website/site', $this->site())->assertRedirect('/login');

        $customer = User::factory()->create(['email_verified_at' => now()]);
        $confirmed = ['auth.password_confirmed_at' => time()];

        $this->actingAs($customer)->withSession($confirmed)->get('/operator/website')->assertForbidden();
        $this->actingAs($customer)->withSession($confirmed)->put('/operator/website/site', $this->site())->assertForbidden();
        $this->actingAs($customer)->withSession($confirmed)->put('/operator/website/team', $this->team(true))->assertForbidden();
        $this->actingAs($customer)->withSession($confirmed)->post('/operator/website/team/photo')->assertForbidden();
        $this->assertDatabaseCount('website_settings', 0);
    }

    public function test_owner_settings_reach_public_pages_and_are_audited(): void
    {
        $site = $this->site();
        $site['features']['kristi'] = false;
        $site['headings']['roadmap']['title'] = 'Where we are going';

        $this->owning()->put('/operator/website/site', $site)->assertSessionHasNoErrors();

        $this->get('/company')->assertInertia(fn (Assert $page) => $page
            ->where('website.features.kristi', false)
            ->where('website.headings.roadmap.title', 'Where we are going')
            ->missing('website.team'));
        $this->assertDatabaseHas('operator_action_audits', ['action' => 'website.settings.updated']);
    }

    public function test_team_page_is_hidden_until_the_owner_publishes_it(): void
    {
        $this->get('/team')->assertNotFound();
        $this->owning()->get('/team')->assertInertia(fn (Assert $page) => $page
            ->component('team')->where('preview', true)->has('members', 4));

        $team = $this->team(true);
        $team['members'][] = [...$team['members'][0], 'name' => 'Hidden person', 'visible' => false];
        $this->owning()->put('/operator/website/team', $team)->assertSessionHasNoErrors();
        auth()->logout();

        $this->get('/team')->assertInertia(fn (Assert $page) => $page
            ->where('preview', false)
            ->has('members', 1)
            ->where('members.0.name', 'Asha Example'));
    }

    public function test_unsafe_profile_links_and_photo_paths_are_rejected(): void
    {
        $team = $this->team(false);
        $team['members'][0]['linkedin'] = 'javascript:alert(1)';
        $team['members'][0]['photo'] = 'https://example.com/photo.png';

        $this->owning()->put('/operator/website/team', $team)
            ->assertSessionHasErrors(['members.0.linkedin', 'members.0.photo']);
        $this->assertDatabaseCount('website_settings', 0);
    }

    public function test_photo_is_private_until_a_published_profile_uses_it(): void
    {
        Storage::fake('local');
        $path = $this->owning()
            ->post('/operator/website/team/photo', ['photo' => UploadedFile::fake()->image('me.png', 200, 200)])
            ->assertCreated()
            ->json('path');
        auth()->logout();
        $this->get($path)->assertStatus(401);

        $team = $this->team(true);
        $team['members'][0]['photo'] = $path;
        $this->owning()->put('/operator/website/team', $team)->assertSessionHasNoErrors();
        auth()->logout();

        $this->get($path)->assertOk()->assertHeader('X-Content-Type-Options', 'nosniff');
    }

    public function test_public_pages_keep_defaults_before_the_migration_runs(): void
    {
        Schema::drop('website_settings');

        $this->get('/company')->assertOk();
        $this->get('/team')->assertNotFound();
        $this->assertSame(WebsiteSettings::defaults()['features'], app(WebsiteSettings::class)->shared()['features']);
        $this->owning()->put('/operator/website/site', $this->site())->assertSessionHasErrors('website');
    }

    private function owning(): self
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'Website control passkey',
            'credential_id' => 'website-control-'.$user->id,
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()]);
    }

    /** @return array<string, mixed> */
    private function site(): array
    {
        $defaults = WebsiteSettings::defaults();

        return array_intersect_key($defaults, array_flip(['features', 'sections', 'headings', 'roadmap']));
    }

    /** @return array<string, mixed> */
    private function team(bool $published): array
    {
        return [
            'published' => $published,
            'intro' => 'Test team.',
            'members' => [[
                'name' => 'Asha Example', 'role' => 'Engineer', 'bio' => null,
                'photo' => null, 'linkedin' => 'https://www.linkedin.com/in/asha-example', 'visible' => true,
            ]],
        ];
    }
}
