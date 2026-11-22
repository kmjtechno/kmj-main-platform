<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class UnverifiedSignupLinkAuditCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_read_only_audit_never_authorizes_deletion_of_signup_organizations(): void
    {
        $old = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(10),
        ]);
        app(OrganizationCreator::class)->create('Unverified signup org', $old->id);

        $recent = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(1),
        ]);
        User::factory()->create(['email_verified_at' => now()]);

        self::assertSame(0, Artisan::call('kmj:users:audit-signup-links', [
            '--days' => '7', '--json' => true,
        ]));
        $result = json_decode(trim(Artisan::output()), true, 512, JSON_THROW_ON_ERROR);
        self::assertSame(2, $result['unverified_users']);
        self::assertSame(1, $result['unverified_nonowner_older_than_cutoff']);
        self::assertSame(1, $result['sampled_with_organization_membership']);
        self::assertFalse($result['safe_to_delete_users']);
        self::assertFalse($result['cross_service_relationships_fully_verified']);
        self::assertSame(0, $result['deleted_users']);
        self::assertSame(0, $result['deleted_organizations']);
        self::assertDatabaseHas('users', ['id' => $old->id]);
        self::assertDatabaseHas('users', ['id' => $recent->id]);
    }

    public function test_all_age_option_still_does_not_mutate_users(): void
    {
        $old = User::factory()->create([
            'email_verified_at' => null,
            'created_at' => now()->subDays(1),
        ]);
        self::assertSame(0, Artisan::call('kmj:users:audit-signup-links', [
            '--days' => '0', '--json' => true,
        ]));
        $result = json_decode(trim(Artisan::output()), true, 512, JSON_THROW_ON_ERROR);
        self::assertSame(1, $result['unverified_nonowner_older_than_cutoff']);
        self::assertFalse($result['safe_to_delete_users']);
        self::assertDatabaseHas('users', ['id' => $old->id]);
    }
}
