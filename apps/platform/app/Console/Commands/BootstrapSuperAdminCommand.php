<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use RuntimeException;

final class BootstrapSuperAdminCommand extends Command
{
    protected $signature = 'kmj:super-admin:bootstrap
        {--apply : Perform a guarded one-time first-account role bootstrap}
        {--confirm= : Required explicit confirmation phrase for --apply}';

    protected $description = 'Inspect or explicitly bootstrap the sole verified passkey account as KMJ Platform Owner';

    public function handle(): int
    {
        $email = config('kmj-super-admin.owner_email');

        if (! is_string($email) || filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
            $this->error('The trusted Super Admin email configuration is invalid.');

            return self::FAILURE;
        }

        if ((bool) $this->option('apply')) {
            if (
                config('kmj-super-admin.bootstrap_enabled') !== true
                || $this->option('confirm') !== 'BOOTSTRAP_VERIFIED_SINGLE_OWNER'
            ) {
                $this->error('Explicit deployment approval and confirmation are required.');

                return self::FAILURE;
            }
        }

        try {
            return DB::transaction(function () use ($email): int {
                // Later unverified registrations must not lock the legitimate
                // first account out. Preserve the first-account identity and
                // fail closed if any competing verified passkey/owner exists.
                $users = User::query()->orderBy('id')->lockForUpdate()->get();
                $verifiedPasskeyAccounts = $users->filter(
                    fn (User $candidate): bool => $candidate->hasVerifiedEmail()
                        && $candidate->passkeys()->exists(),
                );
                if (
                    $users->isEmpty()
                    || $verifiedPasskeyAccounts->count() !== 1
                    || ! $verifiedPasskeyAccounts->first()?->is($users->first())
                    || $users->skip(1)->contains(
                        fn (User $candidate): bool => (bool) $candidate->getAttribute('is_platform_owner'),
                    )
                ) {
                    $this->error('Bootstrap requires the first account to be the sole verified passkey account with no competing platform owner.');

                    return self::FAILURE;
                }

                /** @var User $user */
                $user = $users->first();
                if (
                    ! hash_equals(
                        strtolower(trim($email)),
                        strtolower(trim((string) $user->email)),
                    )
                    || ! $user->hasVerifiedEmail()
                    || ! $user->passkeys()->exists()
                ) {
                    $this->error('The first account must match the verified configured email and have a passkey.');

                    return self::FAILURE;
                }

                if ((bool) $user->getAttribute('is_platform_owner')) {
                    $this->info('Super Admin account already has the platform-owner grant.');

                    return self::SUCCESS;
                }

                if (! (bool) $this->option('apply')) {
                    $this->info('Eligible first account verified; no privileges were changed (dry run).');

                    return self::SUCCESS;
                }

                if (! $this->input->isInteractive()) {
                    $this->error('Role provisioning requires an interactive trusted console.');

                    return self::FAILURE;
                }

                if (! $this->confirm('Grant platform-owner authority to the sole verified passkey account?', false)) {
                    $this->warn('Owner bootstrap cancelled; no privileges were changed.');

                    return self::FAILURE;
                }

                $user->forceFill([
                    'is_platform_owner' => true,
                    'platform_owner_granted_at' => now(),
                ])->save();

                // Do not log credentials, passkey material, or email.
                Log::notice('KMJ_SUPER_ADMIN_BOOTSTRAP_GRANTED', [
                    'user_id' => (string) $user->getKey(),
                ]);
                $this->info('The verified account received platform-owner authority. Re-disable the bootstrap flag.');

                return self::SUCCESS;
            }, 3);
        } catch (RuntimeException $exception) {
            report($exception);
            $this->error('Owner bootstrap could not be completed.');

            return self::FAILURE;
        }
    }
}
