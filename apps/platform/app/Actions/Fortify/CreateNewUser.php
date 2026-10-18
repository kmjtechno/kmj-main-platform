<?php

namespace App\Actions\Fortify;

use App\Concerns\PasswordValidationRules;
use App\Concerns\ProfileValidationRules;
use App\Models\User;
use App\Services\Mail\RegistrationMailReadiness;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\ValidationException;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Laravel\Fortify\Contracts\CreatesNewUsers;

class CreateNewUser implements CreatesNewUsers
{
    use PasswordValidationRules, ProfileValidationRules;

    public function __construct(
        private readonly OrganizationCreator $organizations,
        private readonly RegistrationMailReadiness $registrationMail,
    ) {}

    /**
     * Validate and create a newly registered user with an owner organization.
     *
     * @param  array<string, string>  $input
     */
    public function create(array $input): User
    {
        Validator::make($input, [
            ...$this->profileRules(),
            'password' => $this->passwordRules(),
        ])->validate();

        // A live account that cannot receive its verification link is unusable.
        // Fail before creating the user/organization when the production
        // mailer is log-only, array-only or an unsafe silent fallback.
        if (app()->isProduction() && ! $this->registrationMail->canAttemptDelivery()) {
            throw ValidationException::withMessages([
                'email' => 'Registration is temporarily unavailable because verification email delivery is not configured. Please try later or contact support.',
            ]);
        }

        return DB::transaction(function () use ($input): User {
            $user = User::create([
                'name' => $input['name'],
                'email' => $input['email'],
                'password' => $input['password'],
            ]);

            $this->organizations->create(
                sprintf("%s's Organization", trim($user->name)),
                (int) $user->getKey(),
            );

            return $user;
        });
    }
}
