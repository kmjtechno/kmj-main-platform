<?php

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Hash;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Artisan::command('staging:bootstrap-admin {email} {--name=KMJ Staging Admin}', function () {
    if (! app()->environment('staging')) {
        $this->error('This command is restricted to APP_ENV=staging.');

        return Command::FAILURE;
    }

    $emailArgument = $this->argument('email');
    $nameOption = $this->option('name');

    if (! is_string($emailArgument) || ! is_string($nameOption)) {
        $this->error('Invalid staging admin arguments.');

        return Command::INVALID;
    }

    $email = $emailArgument;
    $name = $nameOption;
    $password = config('kmj.staging_admin_password', '');

    if (! is_string($password)) {
        $this->error('KMJ_STAGING_ADMIN_PASSWORD must be configured as a string.');

        return Command::FAILURE;
    }

    if (filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
        $this->error('A valid staging admin email is required.');

        return Command::INVALID;
    }

    if (mb_strlen($password) < 16) {
        $this->error('KMJ_STAGING_ADMIN_PASSWORD must be set to at least 16 characters.');

        return Command::FAILURE;
    }

    $user = User::query()->updateOrCreate(
        ['email' => $email],
        [
            'name' => $name,
            'password' => Hash::make($password),
            'email_verified_at' => now(),
        ],
    );

    $this->info("Staging admin ready: {$user->email}");

    return Command::SUCCESS;
})->purpose('Create or reset the staging-only control-center operator account');

Artisan::command('staging:promote-platform-owner {email}', function () {
    if (! app()->environment('staging')) {
        $this->error('This command is restricted to APP_ENV=staging.');

        return Command::FAILURE;
    }

    $email = $this->argument('email');
    if (! is_string($email) || filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
        $this->error('A valid staging user email is required.');

        return Command::INVALID;
    }

    $user = User::query()->where('email', $email)->first();
    if (! $user instanceof User) {
        $this->error('Staging user not found.');

        return Command::FAILURE;
    }
    if (! $user->passkeys()->exists()) {
        $this->error('Enroll a passkey before granting platform-owner authority.');

        return Command::FAILURE;
    }

    $user->forceFill(['is_platform_owner' => true, 'platform_owner_granted_at' => now()])->save();
    $this->info('Platform-owner authority granted to the verified staging user.');

    return Command::SUCCESS;
})->purpose('Promote an existing passkey-enabled staging user to platform owner');
