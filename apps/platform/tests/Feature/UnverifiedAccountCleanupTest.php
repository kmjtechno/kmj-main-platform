<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\UnverifiedAccountCleanup;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
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
}
