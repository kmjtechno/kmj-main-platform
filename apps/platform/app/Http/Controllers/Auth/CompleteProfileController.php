<?php

namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use App\Models\CustomerProfile;
use App\Models\User;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Inertia\Inertia;
use Inertia\Response;

/** Contact details collected after sign-in (for example after Google sign-up). Not an entitlement. */
final class CompleteProfileController extends Controller
{
    public function show(Request $request): Response|RedirectResponse
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        if ($user->customerProfile()->exists()) {
            return redirect()->route('dashboard');
        }

        return Inertia::render('auth/complete-profile', ['email' => $user->email]);
    }

    public function store(Request $request): RedirectResponse
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'account_type' => ['required', Rule::in(['individual', 'business'])],
            'phone' => ['required', 'string', 'max:32', 'regex:/^\\+?[0-9][0-9 .()\\-]{6,30}$/'],
            'country' => ['required', 'string', 'min:2', 'max:80'],
            'company_name' => ['exclude_unless:account_type,business', 'required_if:account_type,business', 'string', 'min:2', 'max:160'],
            'service_interest' => ['nullable', Rule::in([
                'software', 'cloud', 'remote_access', 'calibration', 'cinema', 'other',
            ])],
        ]);

        CustomerProfile::query()->updateOrCreate(
            ['user_id' => $user->getKey()],
            [
                'account_type' => $validated['account_type'],
                'phone' => trim($validated['phone']),
                'country' => trim($validated['country']),
                'company_name' => isset($validated['company_name']) ? trim($validated['company_name']) : null,
                'service_interest' => $validated['service_interest'] ?? null,
            ],
        );

        return redirect()->intended(route('dashboard', absolute: false));
    }
}
