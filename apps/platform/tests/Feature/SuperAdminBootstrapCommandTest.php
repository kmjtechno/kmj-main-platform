<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class SuperAdminBootstrapCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_first_account_is_never_promoted_by_dry_run(): void
    {
        $user = $this->createSingleAccount(withPasskey: true);
        $this->artisan('kmj:super-admin:bootstrap')
            ->expectsOutput('Eligible first account verified; no privileges were changed (dry run).')
            ->assertExitCode(0);

        self::assertFalse((bool) $user->fresh()?->getAttribute('is_platform_owner'));
    }

    public function test_apply_requires_explicit_configuration_and_confirmation(): void
    {
        $user = $this->createSingleAccount(withPasskey: true);

        $this->artisan('kmj:super-admin:bootstrap', [
            '--apply' => true,
            '--confirm' => 'BOOTSTRAP_VERIFIED_SINGLE_OWNER',
        ])->assertExitCode(1);

        config()->set('kmj-super-admin.bootstrap_enabled', true);

        $this->artisan('kmj:super-admin:bootstrap', [
            '--apply' => true,
            '--confirm' => 'wrong',
        ])->assertExitCode(1);

        self::assertFalse((bool) $user->fresh()?->getAttribute('is_platform_owner'));
    }

    public function test_bootstrap_rejects_wrong_email_unverified_account_missing_passkey_and_multiple_users(): void
    {
        $user = $this->createSingleAccount(withPasskey: false);

        $this->artisan('kmj:super-admin:bootstrap')->assertExitCode(1);

        $this->installPasskey($user);
        $user->forceFill(['email_verified_at' => null])->save();
        $this->artisan('kmj:super-admin:bootstrap')->assertExitCode(1);

        $user->forceFill([
            'email_verified_at' => now(),
            'email' => 'different.owner@example.test',
        ])->save();
        $this->artisan('kmj:super-admin:bootstrap')->assertExitCode(1);

        $user->forceFill(['email' => 'kmjtechno.net@gmail.com'])->save();
        User::factory()->create();
        $this->artisan('kmj:super-admin:bootstrap')->assertExitCode(1);

        self::assertSame(0, DB::table('users')->where('is_platform_owner', true)->count());
    }

    public function test_explicit_interactive_bootstrap_grants_only_the_verified_first_account(): void
    {
        $user = $this->createSingleAccount(withPasskey: true);
        config()->set('kmj-super-admin.bootstrap_enabled', true);

        $this->artisan('kmj:super-admin:bootstrap', [
            '--apply' => true,
            '--confirm' => 'BOOTSTRAP_VERIFIED_SINGLE_OWNER',
        ])
            ->expectsConfirmation('Grant platform-owner authority to the sole verified passkey account?', 'yes')
            ->assertExitCode(0);

        $activated = $user->fresh();
        self::assertTrue((bool) $activated?->getAttribute('is_platform_owner'));
        self::assertNotNull($activated?->getAttribute('platform_owner_granted_at'));

        // A second call is an idempotent status check, not a new grant.
        $grantedAt = (string) $activated->getAttribute('platform_owner_granted_at');
        $this->artisan('kmj:super-admin:bootstrap')->assertExitCode(0);
        self::assertSame(
            $grantedAt,
            (string) $user->fresh()?->getAttribute('platform_owner_granted_at'),
        );
    }

    public function test_confirmation_cancellation_never_mutates_the_account(): void
    {
        $user = $this->createSingleAccount(withPasskey: true);
        config()->set('kmj-super-admin.bootstrap_enabled', true);

        $this->artisan('kmj:super-admin:bootstrap', [
            '--apply' => true,
            '--confirm' => 'BOOTSTRAP_VERIFIED_SINGLE_OWNER',
        ])
            ->expectsConfirmation('Grant platform-owner authority to the sole verified passkey account?', 'no')
            ->assertExitCode(1);

        self::assertFalse((bool) $user->fresh()?->getAttribute('is_platform_owner'));
    }

    private function createSingleAccount(bool $withPasskey): User
    {
        $user = User::factory()->create([
            'email' => 'kmjtechno.net@gmail.com',
            'email_verified_at' => now(),
            'is_platform_owner' => false,
        ]);
        if ($withPasskey) {
            $this->installPasskey($user);
        }

        return $user;
    }

    private function installPasskey(User $user): void
    {
        DB::table('passkeys')->insert([
            'user_id' => $user->getKey(),
            'name' => 'Super Admin test passkey',
            'credential_id' => 'super-admin-test-'.$user->getKey(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }
}
