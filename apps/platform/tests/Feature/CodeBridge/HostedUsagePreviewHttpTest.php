<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class HostedUsagePreviewHttpTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_guest_and_unverified_user_cannot_open_customer_usage_preview(): void
    {
        $this->get('/licensing')->assertRedirect('/login');
        $unverified = User::factory()->create(['email_verified_at' => null]);
        $this->actingAs($unverified)->get('/licensing')
            ->assertRedirect(route('verification.notice'));
    }

    public function test_verified_customer_sees_proposal_but_not_fabricated_usage_or_checkout(): void
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        $response = $this->actingAs($customer)->get('/licensing');

        $response->assertOk()->assertInertia(fn (Assert $page) => $page
            ->component('licensing-hub')
            ->where('codebridge_usage_preview.status', 'proposal_only')
            ->where('codebridge_usage_preview.meter_live', false)
            ->where('codebridge_usage_preview.checkout_live', false)
            ->where('codebridge_usage_preview.trial_live', false)
            ->where('codebridge_usage_preview.active_plan', null)
            ->where('codebridge_usage_preview.used_calls', null)
            ->where('codebridge_usage_preview.remaining_calls', null)
            ->where('codebridge_usage_preview.next_reset_at', null)
            ->where('codebridge_usage_preview.self_hosted_unmetered', true)
            ->where('codebridge_usage_preview.ai_provider_fees_included', false)
            ->has('codebridge_usage_preview.plans', 4)
            ->where('codebridge_usage_preview.plans.0.monthly_calls', 10000)
            ->where('codebridge_usage_preview.plans.0.monthly_price_inr', 0)
            ->where('codebridge_usage_preview.plans.1.monthly_calls', 100000)
            ->where('codebridge_usage_preview.plans.1.monthly_price_inr', 299)
            ->where('codebridge_usage_preview.plans.2.monthly_calls', 300000)
            ->where('codebridge_usage_preview.plans.2.monthly_price_inr', 699)
            ->where('codebridge_usage_preview.plans.2.per_user', true));

        $this->assertStringContainsString(
            'no-store',
            strtolower((string) $response->headers->get('Cache-Control')),
        );
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_other_tenant_monthly_reservations_do_not_leak_through_customer_preview(): void
    {
        $customer = User::factory()->create(['email_verified_at' => now()]);
        $foreignOrganization = (string) Str::uuid();
        $foreignSubject = 'seat:another-customer';
        DB::table('codebridge_usage_periods')->insert([
            'organization_id' => $foreignOrganization,
            'subject_key' => $foreignSubject,
            'period_start_utc' => '2026-11-01',
            'plan_code' => 'team',
            'monthly_limit' => 300000,
            'reserved_calls' => 7,
            'completed_calls' => 9876,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $response = $this->actingAs($customer)
            ->get('/licensing?organization_id='.$foreignOrganization.'&subject_key='.$foreignSubject);
        $response->assertOk()->assertInertia(fn (Assert $page) => $page
            ->where('codebridge_usage_preview.status', 'proposal_only')
            ->where('codebridge_usage_preview.used_calls', null)
            ->where('codebridge_usage_preview.remaining_calls', null)
            ->where('codebridge_usage_preview.active_plan', null));
        $body = (string) $response->getContent();
        self::assertStringNotContainsString($foreignOrganization, $body);
        self::assertStringNotContainsString($foreignSubject, $body);
        self::assertStringNotContainsString('9876', $body);
        $this->assertDatabaseCount('codebridge_usage_periods', 1);
    }
}
