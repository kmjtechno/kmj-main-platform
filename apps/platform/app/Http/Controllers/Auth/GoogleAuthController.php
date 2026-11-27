<?php

namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use App\Models\User;
use App\Services\Auth\GoogleSignIn;
use DomainException;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;

/**
 * Register or sign in with Google. Contact details (phone, country, company) are collected after
 * sign-in on the profile page. A Google login never bypasses a passkey or two-factor on an account.
 */
final class GoogleAuthController extends Controller
{
    public function __construct(
        private readonly GoogleSignIn $google,
        private readonly OrganizationCreator $organizations,
    ) {}

    public function redirect(Request $request): RedirectResponse
    {
        if (! $this->google->enabled()) {
            return redirect()->route('login');
        }

        return redirect()->away($this->google->authorizationUrl($request));
    }

    public function callback(Request $request): RedirectResponse
    {
        try {
            $profile = $this->google->profileFromCallback($request);
        } catch (DomainException $error) {
            Log::notice('google_signin.rejected', ['code' => $error->getMessage()]);

            return $this->failed('Google sign-in could not be completed. Please try again or use your email and password.');
        }

        $user = $this->resolveUser($profile);
        if ($user === null) {
            return $this->failed('This account is protected with a passkey or two-factor sign-in. Please sign in that way.');
        }

        Auth::login($user);
        $request->session()->regenerate();

        return $user->customerProfile()->exists()
            ? redirect()->intended(route('dashboard', absolute: false))
            : redirect()->route('onboarding.profile.show');
    }

    /** @param array{sub: string, email: string, name: string} $profile */
    private function resolveUser(array $profile): ?User
    {
        $identity = DB::table('oauth_identities')
            ->where('provider', 'google')->where('provider_user_id', $profile['sub'])->first();

        $user = $identity !== null
            ? User::query()->find($identity->user_id)
            : User::query()->whereRaw('lower(email) = ?', [$profile['email']])->first();

        if ($user instanceof User) {
            if ($this->hasStrongSignIn($user)) {
                return null;
            }

            return DB::transaction(function () use ($user, $profile, $identity): User {
                if ($user->email_verified_at === null) {
                    // Google just proved control of this address. Anyone who pre-registered it with a
                    // password they know must not keep access, so the old password is replaced.
                    $user->forceFill([
                        'email_verified_at' => now(),
                        'password' => Hash::make(Str::random(48)),
                    ])->save();
                }
                if ($identity === null) {
                    $this->linkIdentity($user, $profile['sub']);
                }

                return $user;
            });
        }

        return DB::transaction(function () use ($profile): User {
            $user = User::create([
                'name' => $profile['name'],
                'email' => $profile['email'],
                'password' => Str::random(48),
            ]);
            $user->forceFill(['email_verified_at' => now()])->save();
            $this->linkIdentity($user, $profile['sub']);
            $this->organizations->create(sprintf("%s's Organization", $user->name), (int) $user->getKey());

            return $user;
        });
    }

    private function linkIdentity(User $user, string $sub): void
    {
        DB::table('oauth_identities')->insert([
            'user_id' => $user->getKey(),
            'provider' => 'google',
            'provider_user_id' => $sub,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    private function hasStrongSignIn(User $user): bool
    {
        return $user->two_factor_confirmed_at !== null
            || DB::table('passkeys')->where('user_id', $user->getKey())->exists();
    }

    private function failed(string $message): RedirectResponse
    {
        return redirect()->route('login')->withErrors(['email' => $message]);
    }
}
