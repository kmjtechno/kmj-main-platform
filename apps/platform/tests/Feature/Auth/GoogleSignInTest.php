<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class GoogleSignInTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('services.google_signin.client_id', 'test-client-id.apps.googleusercontent.com');
        config()->set('services.google_signin.client_secret', 'test-client-secret');
    }

    /** Starts the flow and returns the state the server stored in the session. */
    private function startFlow(): string
    {
        $response = $this->get('/auth/google/redirect');
        $response->assertRedirect();
        $location = (string) $response->headers->get('Location');
        self::assertStringStartsWith('https://accounts.google.com/o/oauth2/v2/auth?', $location);
        parse_str((string) parse_url($location, PHP_URL_QUERY), $query);
        self::assertSame('S256', $query['code_challenge_method']);
        self::assertSame('openid email profile', $query['scope']);
        self::assertSame('test-client-id.apps.googleusercontent.com', $query['client_id']);

        return (string) $query['state'];
    }

    /** @param array<string, mixed> $userinfo */
    private function fakeGoogle(array $userinfo): void
    {
        Http::preventStrayRequests();
        Http::fake([
            'oauth2.googleapis.com/token' => Http::response(['access_token' => 'at-123'], 200),
            'openidconnect.googleapis.com/v1/userinfo' => Http::response($userinfo, 200),
        ]);
    }

    public function test_button_flag_is_off_without_credentials_and_the_flow_is_closed(): void
    {
        config()->set('services.google_signin.client_id', '');
        config()->set('services.google_signin.client_secret', '');

        $this->get('/auth/google/redirect')->assertRedirect(route('login'));
        $this->get('/auth/google/callback?state=x&code=y')
            ->assertRedirect(route('login'))->assertSessionHasErrors('email');
        $this->assertSame(0, User::query()->count());
    }

    public function test_new_google_user_is_created_verified_with_an_organization_and_no_profile_yet(): void
    {
        $state = $this->startFlow();
        $this->fakeGoogle([
            'sub' => 'g-sub-1', 'email' => 'New.Person@Example.com', 'email_verified' => true, 'name' => 'New Person',
        ]);

        $this->get('/auth/google/callback?state='.$state.'&code=abc')
            ->assertRedirect(route('onboarding.profile.show'));

        $user = User::query()->where('email', 'new.person@example.com')->firstOrFail();
        $this->assertAuthenticatedAs($user);
        $this->assertNotNull($user->email_verified_at);
        $this->assertDatabaseHas('oauth_identities', ['user_id' => $user->id, 'provider' => 'google', 'provider_user_id' => 'g-sub-1']);
        $this->assertDatabaseHas('organizations', ['name' => "New Person's Organization"]);
        $this->assertDatabaseMissing('customer_profiles', ['user_id' => $user->id]);

        Http::assertSent(fn (ClientRequest $r): bool => $r->url() === 'https://oauth2.googleapis.com/token'
            && isset($r['code_verifier']) && $r['code'] === 'abc');
    }

    public function test_profile_page_collects_contact_details_after_sign_in(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)->get('/onboarding/profile')->assertOk();
        $this->actingAs($user)->post('/onboarding/profile', [
            'account_type' => 'business',
            'company_name' => 'Acme Labs',
            'phone' => '+91 98765 43210',
            'country' => 'India',
        ])->assertRedirect(route('dashboard', absolute: false));

        $this->assertDatabaseHas('customer_profiles', [
            'user_id' => $user->id, 'account_type' => 'business', 'company_name' => 'Acme Labs',
        ]);
        $this->actingAs($user)->get('/onboarding/profile')->assertRedirect(route('dashboard'));
    }

    public function test_unverified_email_from_google_is_refused(): void
    {
        $state = $this->startFlow();
        $this->fakeGoogle(['sub' => 'g-2', 'email' => 'x@example.com', 'email_verified' => false, 'name' => 'X']);

        $this->get('/auth/google/callback?state='.$state.'&code=abc')
            ->assertRedirect(route('login'))->assertSessionHasErrors('email');
        $this->assertGuest();
        $this->assertSame(0, User::query()->count());
    }

    public function test_wrong_or_missing_state_is_refused_before_any_google_call(): void
    {
        Http::preventStrayRequests();
        $this->startFlow();

        $this->get('/auth/google/callback?state=wrong&code=abc')
            ->assertRedirect(route('login'))->assertSessionHasErrors('email');
        $this->get('/auth/google/callback?state=wrong&code=abc')->assertSessionHasErrors('email');
        $this->assertGuest();
        $this->assertSame(0, User::query()->count());
    }

    public function test_existing_verified_user_is_linked_and_signed_in(): void
    {
        $user = User::factory()->create(['email' => 'known@example.com']);
        $state = $this->startFlow();
        $this->fakeGoogle(['sub' => 'g-3', 'email' => 'known@example.com', 'email_verified' => true, 'name' => 'Known']);

        $this->get('/auth/google/callback?state='.$state.'&code=abc')->assertRedirect();

        $this->assertAuthenticatedAs($user);
        $this->assertSame(1, User::query()->count());
        $this->assertDatabaseHas('oauth_identities', ['user_id' => $user->id, 'provider_user_id' => 'g-3']);
    }

    public function test_preregistered_unverified_account_loses_its_old_password_when_the_real_owner_signs_in(): void
    {
        $attacker = User::factory()->unverified()->create([
            'email' => 'victim@example.com',
            'password' => Hash::make('attacker-known-password'),
        ]);
        $state = $this->startFlow();
        $this->fakeGoogle(['sub' => 'g-4', 'email' => 'victim@example.com', 'email_verified' => true, 'name' => 'Victim']);

        $this->get('/auth/google/callback?state='.$state.'&code=abc')->assertRedirect();

        $attacker->refresh();
        $this->assertNotNull($attacker->email_verified_at);
        $this->assertFalse(Hash::check('attacker-known-password', $attacker->password));
    }

    public function test_account_with_a_passkey_cannot_be_entered_through_google(): void
    {
        $user = User::factory()->create(['email' => 'secure@example.com']);
        DB::table('passkeys')->insert([
            'user_id' => $user->id, 'name' => 'Key', 'credential_id' => 'cred-1',
            'credential' => '{}', 'created_at' => now(), 'updated_at' => now(),
        ]);
        $state = $this->startFlow();
        $this->fakeGoogle(['sub' => 'g-5', 'email' => 'secure@example.com', 'email_verified' => true, 'name' => 'Secure']);

        $this->get('/auth/google/callback?state='.$state.'&code=abc')
            ->assertRedirect(route('login'))->assertSessionHasErrors('email');
        $this->assertGuest();
        $this->assertDatabaseMissing('oauth_identities', ['user_id' => $user->id]);
    }

    public function test_provider_rejection_is_shown_as_a_generic_message(): void
    {
        $state = $this->startFlow();
        Http::preventStrayRequests();
        Http::fake(['oauth2.googleapis.com/token' => Http::response(['error' => 'invalid_grant'], 400)]);

        $this->get('/auth/google/callback?state='.$state.'&code=abc')
            ->assertRedirect(route('login'))->assertSessionHasErrors('email');
        $this->assertGuest();
    }
}
