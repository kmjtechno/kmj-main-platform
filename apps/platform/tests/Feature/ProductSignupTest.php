<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Commerce\KmjProductCatalog;
use App\Services\Commerce\ProductSignups;
use Illuminate\Auth\Events\Verified;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class ProductSignupTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        app(KmjProductCatalog::class)->syncAll();
    }

    private function customer(bool $verified = true): User
    {
        $user = User::factory()->create(['email_verified_at' => $verified ? now() : null]);
        app(OrganizationCreator::class)->create('Signup Org '.$user->id, (int) $user->id);

        return $user;
    }

    public function test_verified_cloudos_signup_gets_one_expiring_trial_and_matching_access(): void
    {
        $user = $this->customer();

        $this->actingAs($user)->post('/product-signups', ['product' => 'kmj-cloudos'])
            ->assertRedirect(route('dashboard'));
        $this->actingAs($user)->post('/product-signups', ['product' => 'kmj-cloudos'])
            ->assertRedirect(route('dashboard'));

        $this->assertSame(1, DB::table('kslp_licenses')->where('customer_id', (string) $user->id)->count());
        $license = DB::table('kslp_licenses')->first();
        $this->assertSame('trial', $license->plan);
        $this->assertSame(1, Entitlement::query()->count());
        $access = Entitlement::query()->firstOrFail();
        $this->assertNotNull($access->ends_at);
        $this->assertSame(
            strtotime((string) $license->expires_at),
            $access->ends_at->getTimestamp(),
        );
        $this->assertDatabaseHas('product_signups', ['user_id' => $user->id, 'state' => ProductSignups::TRIAL_STARTED]);

        // After the trial ends the access no longer reads as switched on.
        $this->travel(31)->days();
        $this->actingAs($user)->get('/dashboard')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('organizations.0.entitlements.0.status', 'expired'));
    }

    public function test_unverified_signup_waits_until_the_email_is_verified(): void
    {
        $user = $this->customer(false);
        app(ProductSignups::class)->record($user, 'kmj-cloudos');

        $this->assertSame(0, DB::table('kslp_licenses')->count());
        $this->assertSame(0, Entitlement::query()->count());

        $user->markEmailAsVerified();
        event(new Verified($user));

        $this->assertSame(1, DB::table('kslp_licenses')->count());
        $this->assertSame(1, Entitlement::query()->count());
    }

    public function test_unready_product_is_only_pre_registered(): void
    {
        $user = $this->customer();

        $this->actingAs($user)->post('/product-signups', ['product' => 'kmj-omnidesk'])
            ->assertRedirect(route('dashboard'));

        $this->assertDatabaseHas('product_signups', ['product_slug' => 'kmj-omnidesk', 'state' => ProductSignups::WAITING]);
        $this->assertSame(0, DB::table('kslp_licenses')->count());
        $this->assertSame(0, Entitlement::query()->count());
    }

    public function test_switching_the_trial_off_grants_nothing(): void
    {
        config(['services.kmj_signup_trial.enabled' => false]);
        $user = $this->customer();

        $this->actingAs($user)->post('/product-signups', ['product' => 'kmj-cloudos']);

        $this->assertSame(0, DB::table('kslp_licenses')->count());
        $this->assertSame(0, Entitlement::query()->count());
    }

    public function test_guests_unverified_users_and_unknown_products_are_refused(): void
    {
        $this->post('/product-signups', ['product' => 'kmj-cloudos'])->assertRedirect('/login');
        $this->actingAs($this->customer(false))
            ->post('/product-signups', ['product' => 'kmj-cloudos'])
            ->assertRedirect(route('verification.notice'));
        $this->actingAs($this->customer())
            ->post('/product-signups', ['product' => 'not-a-product'])
            ->assertNotFound();

        $this->assertSame(0, DB::table('product_signups')->count());
    }

    public function test_register_page_remembers_the_product_through_sign_in(): void
    {
        $user = $this->customer();

        $this->get('/register?product=kmj-cloudos')
            ->assertOk()
            ->assertSessionHas('kmj_signup_product', 'kmj-cloudos');

        $this->post('/login', ['email' => $user->email, 'password' => 'password']);

        $this->assertDatabaseHas('product_signups', ['user_id' => $user->id, 'product_slug' => 'kmj-cloudos']);
    }
}
