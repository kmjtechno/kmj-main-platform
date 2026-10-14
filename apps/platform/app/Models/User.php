<?php

namespace App\Models;

use App\Services\Mail\RegistrationMailReadiness;
use Database\Factories\UserFactory;
use Illuminate\Auth\Notifications\ResetPassword;
use Illuminate\Auth\Notifications\VerifyEmail;
use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Attributes\Hidden;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Illuminate\Validation\ValidationException;
use Illuminate\Support\Carbon;
use Laravel\Fortify\Contracts\PasskeyUser;
use Laravel\Fortify\PasskeyAuthenticatable;
use Laravel\Fortify\TwoFactorAuthenticatable;

/**
 * @property int $id
 * @property string $name
 * @property string $email
 * @property Carbon|null $email_verified_at
 * @property string $password
 * @property string|null $two_factor_secret
 * @property string|null $two_factor_recovery_codes
 * @property Carbon|null $two_factor_confirmed_at
 * @property string|null $remember_token
 * @property Carbon|null $created_at
 * @property Carbon|null $updated_at
 */
#[Fillable(['name', 'email', 'password'])]
#[Hidden(['password', 'two_factor_secret', 'two_factor_recovery_codes', 'remember_token'])]
class User extends Authenticatable implements MustVerifyEmail, PasskeyUser
{
    /** @use HasFactory<UserFactory> */
    use HasFactory, Notifiable, PasskeyAuthenticatable, TwoFactorAuthenticatable;

    /**
     * A queued/logged Laravel notification is NOT evidence of mail delivery.
     * Prevent the Fortify resend endpoint from returning false success while
     * production transport is log-only, array-only or has an unsafe fallback.
     */
    public function sendEmailVerificationNotification(): void
    {
        if (app()->isProduction() && ! app(RegistrationMailReadiness::class)->canAttemptDelivery()) {
            throw ValidationException::withMessages([
                'email' => 'Verification email delivery is temporarily unavailable. Please try again later.',
            ]);
        }

        $this->notify(new VerifyEmail);
    }

    /**
     * Password resets must not be acknowledged by a log-only mailer.
     */
    public function sendPasswordResetNotification($token): void
    {
        if (app()->isProduction() && ! app(RegistrationMailReadiness::class)->canAttemptDelivery()) {
            throw ValidationException::withMessages([
                'email' => 'Password reset email delivery is temporarily unavailable. Please try again later.',
            ]);
        }

        $this->notify(new ResetPassword($token));
    }

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
            'is_platform_owner' => 'boolean',
            'platform_owner_granted_at' => 'datetime',
            /* @chisel-2fa */
            'two_factor_confirmed_at' => 'datetime',
            /* @end-chisel-2fa */
        ];
    }
}
