<?php

namespace App\Actions\Fortify;

use App\Concerns\PasswordValidationRules;
use App\Concerns\ProfileValidationRules;
use App\Models\CustomerProfile;
use App\Models\User;
use App\Services\Mail\RegistrationMailReadiness;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\Rule;
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
        $validated = Validator::make($input, [
            ...$this->profileRules(),
            'password' => $this->passwordRules(),
            'account_type' => ['required', Rule::in(['individual', 'business'])],
            'phone' => ['required', 'string', 'max:32', 'regex:/^\\+?[0-9][0-9 .()\\-]{6,30}$/'],
            'country' => ['required', 'string', 'min:2', 'max:80'],
            'company_name' => ['exclude_unless:account_type,business', 'required_if:account_type,business', 'string', 'min:2', 'max:160'],
            'service_interest' => ['nullable', Rule::in([
                'software', 'cloud', 'remote_access', 'calibration', 'cinema', 'other',
            ])],
        ])->validate();

        // A live account that cannot receive its verification link is unusable.
        // Fail before creating the user/organization when the production
        // mailer is log-only, array-only or an unsafe silent fallback.
        if (app()->isProduction() && ! $this->registrationMail->canAttemptDelivery()) {
            throw ValidationException::withMessages([
                'email' => 'Registration is temporarily unavailable because verification email delivery is not configured. Please try later or contact support.',
            ]);
        }

        return DB::transaction(function () use ($validated): User {
            $user = User::create([
                'name' => trim($validated['name']),
                'email' => trim($validated['email']),
                'password' => $validated['password'],
            ]);

            // A private account contact record, NOT an entitlement, license,
            // email verification or high-assurance organization approval.
            CustomerProfile::query()->create([
                'user_id' => $user->getKey(),
                'account_type' => $validated['account_type'],
                'phone' => trim($validated['phone']),
                'country' => trim($validated['country']),
                'company_name' => isset($validated['company_name'])
                    ? trim($validated['company_name'])
                    : null,
                'service_interest' => $validated['service_interest'] ?? null,
            ]);

            $organizationName = $validated['account_type'] === 'business'
                ? trim($validated['company_name'])
                : sprintf("%s's Organization", trim($user->name));

            $this->organizations->create($organizationName, (int) $user->getKey());

            return $user;
        });
    }
}
