<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\Licensing\UnverifiedAccountCleanup;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;
use RuntimeException;
use Tests\TestCase;

final class UnverifiedAccountCleanupTest extends TestCase
{
    use RefreshDatabase;

    public function test_exact_preview_deletes_only_old_standalone_unverified_user(): void
    {
        $old = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(12),
        ]);
        $linked = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(12),
        ]);
        $recent = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDay(),
        ]);
        $verified = User::factory()->create([
            'email_verified_at' => now(),
            'created_at' => now()->subDays(12),
        ]);

        $orgId = (string) Str::uuid();
        DB::table('organizations')->insert([
            'id' => $orgId,
            'name' => 'Protected Issuer Membership',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $orgId,
            'user_id' => $linked->id,
            'role' => 'owner',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        // A second member makes the organization real: the account is not its only member.
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $orgId,
            'user_id' => $verified->id,
            'role' => 'member',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $cleanup = app(UnverifiedAccountCleanup::class);
        $preview = $cleanup->preview();
        $this->assertSame(3, $preview['unverified']);
        $this->assertSame(1, $preview['eligible']);
        $this->assertSame(2, $preview['protected']);
        $this->assertSame([$old->id], $preview['candidateIds']);

        $this->assertSame(1, $cleanup->purge(1, $preview['sha256']));
        $this->assertDatabaseMissing('users', ['id' => $old->id]);
        $this->assertDatabaseHas('users', ['id' => $linked->id]);
        $this->assertDatabaseHas('users', ['id' => $recent->id]);
        $this->assertDatabaseHas('users', ['id' => $verified->id]);
        $this->assertDatabaseHas('organization_memberships', [
            'user_id' => $linked->id,
            'organization_id' => $orgId,
        ]);
    }

    public function test_verified_after_preview_is_not_deleted(): void
    {
        $old = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(10),
        ]);
        $cleanup = app(UnverifiedAccountCleanup::class);
        $preview = $cleanup->preview();
        $this->assertSame(1, $preview['eligible']);

        $old->forceFill(['email_verified_at' => now()])->save();

        $this->expectException(RuntimeException::class);
        try {
            $cleanup->purge(1, $preview['sha256']);
        } finally {
            $this->assertDatabaseHas('users', ['id' => $old->id]);
        }
    }

    public function test_mismatched_preview_never_deletes_old_unverified_user(): void
    {
        $old = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(10),
        ]);
        $cleanup = app(UnverifiedAccountCleanup::class);
        $this->expectException(RuntimeException::class);
        try {
            $cleanup->purge(1, str_repeat('f', 64));
        } finally {
            $this->assertDatabaseHas('users', ['id' => $old->id]);
        }
    }

    private function signupOrganization(User $user): string
    {
        $orgId = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $orgId, 'name' => 'Signup Org', 'created_at' => now(), 'updated_at' => now()]);
        DB::table('organization_memberships')->insert([
            'id' => (string) Str::uuid(),
            'organization_id' => $orgId,
            'user_id' => $user->id,
            'role' => 'owner',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $orgId;
    }

    public function test_sole_owner_of_an_empty_signup_organization_is_removed_with_it_and_its_profile(): void
    {
        $old = User::factory()->create(['email_verified_at' => null, 'created_at' => now()->subDays(12)]);
        $orgId = $this->signupOrganization($old);
        DB::table('customer_profiles')->insert([
            'user_id' => $old->id, 'account_type' => 'individual', 'phone' => '+910000000000',
            'country' => 'India', 'created_at' => now(), 'updated_at' => now(),
        ]);

        $cleanup = app(UnverifiedAccountCleanup::class);
        $preview = $cleanup->preview();
        $this->assertSame([$old->id], $preview['candidateIds']);

        $this->assertSame(1, $cleanup->purge(1, $preview['sha256']));
        $this->assertDatabaseMissing('users', ['id' => $old->id]);
        $this->assertDatabaseMissing('organizations', ['id' => $orgId]);
        $this->assertDatabaseMissing('organization_memberships', ['organization_id' => $orgId]);
        $this->assertDatabaseMissing('customer_profiles', ['user_id' => $old->id]);
    }

    public function test_an_organization_referenced_by_any_other_table_keeps_the_account_protected(): void
    {
        $old = User::factory()->create(['email_verified_at' => null, 'created_at' => now()->subDays(12)]);
        $orgId = $this->signupOrganization($old);
        AiProvider::query()->create([
            'organization_id' => $orgId, 'name' => 'Referenced', 'preset' => 'github', 'kind' => 'openai-compatible',
            'base_url' => 'https://models.github.ai/inference', 'api_key' => 'github_pat_test_key_123456',
            'key_last4' => '3456', 'enabled' => true, 'free_only' => true,
        ]);

        $preview = app(UnverifiedAccountCleanup::class)->preview();
        $this->assertSame(0, $preview['eligible']);
        $this->assertSame(1, $preview['protected']);
        $this->assertDatabaseHas('users', ['id' => $old->id]);
        $this->assertDatabaseHas('organizations', ['id' => $orgId]);
    }

    public function test_a_reference_added_after_the_preview_aborts_the_purge_and_keeps_everything(): void
    {
        $old = User::factory()->create(['email_verified_at' => null, 'created_at' => now()->subDays(12)]);
        $orgId = $this->signupOrganization($old);
        $cleanup = app(UnverifiedAccountCleanup::class);
        $preview = $cleanup->preview();
        $this->assertSame(1, $preview['eligible']);

        AiProvider::query()->create([
            'organization_id' => $orgId, 'name' => 'Late', 'preset' => 'github', 'kind' => 'openai-compatible',
            'base_url' => 'https://models.github.ai/inference', 'api_key' => 'github_pat_test_key_123456',
            'key_last4' => '3456', 'enabled' => true, 'free_only' => true,
        ]);

        try {
            $cleanup->purge(1, $preview['sha256']);
            $this->fail('A stale preview must abort the purge.');
        } catch (RuntimeException) {
            $this->assertDatabaseHas('users', ['id' => $old->id]);
            $this->assertDatabaseHas('organizations', ['id' => $orgId]);
        }
    }

    public function test_json_organization_reference_requires_schema_review_before_a_cleanup_preview(): void
    {
        if (DB::getDriverName() !== 'pgsql') {
            $this->markTestSkipped('PostgreSQL JSONB column introspection is required.');
        }

        $old = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(12),
        ]);
        $orgId = $this->signupOrganization($old);

        // An organization UUID may be embedded in a JSON document even without
        // a foreign key. Unknown references must block cleanup, not be ignored.
        Schema::create('cleanup_json_reference_witness', function (Blueprint $table): void {
            $table->id();
            $table->jsonb('organization_reference');
        });
        DB::table('cleanup_json_reference_witness')->insert([
            'organization_reference' => json_encode(['organization_id' => $orgId], JSON_THROW_ON_ERROR),
        ]);

        $cleanup = app(UnverifiedAccountCleanup::class);
        try {
            $cleanup->preview();
            $this->fail('An unreviewed JSON organization reference must block cleanup.');
        } catch (RuntimeException $e) {
            $this->assertSame('UNVERIFIED_CLEANUP_ORG_REFERENCE_TYPE_UNKNOWN', $e->getMessage());
        }

        $this->assertDatabaseHas('users', ['id' => $old->id]);
        $this->assertDatabaseHas('organizations', ['id' => $orgId]);
    }

}
