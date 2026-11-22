<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\Directory\OwnerDirectoryAccountActions;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Validation\ValidationException;
use Inertia\Inertia;
use KMJ\MainPlatform\Organizations\Models\Organization;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator')
    ->name('operator.')
    ->group(function (): void {
        Route::get('directory', function (Request $request, PlatformOwnerAccess $access) {
            $actor = $request->user();
            abort_unless($actor instanceof User, 401);
            $access->require($actor);

            $filters = $request->validate([
                'users_q' => ['sometimes', 'nullable', 'string', 'max:80'],
                'users_status' => ['sometimes', 'in:all,verified,unverified'],
                'orgs_q' => ['sometimes', 'nullable', 'string', 'max:80'],
                'users_page' => ['sometimes', 'integer', 'min:1', 'max:100000'],
                'orgs_page' => ['sometimes', 'integer', 'min:1', 'max:100000'],
            ]);

            $userFilter = trim((string) ($filters['users_q'] ?? ''));
            $orgFilter = trim((string) ($filters['orgs_q'] ?? ''));
            $statusFilter = (string) ($filters['users_status'] ?? 'all');

            // Read-only discovery with explicit columns; never serialize the
            // authentication model (password, passkeys, tokens or recovery).
            $users = User::query()
                ->select(['id', 'name', 'email', 'email_verified_at', 'created_at', 'is_platform_owner'])
                // Explicit allowlist of business/contact fields: never expose
                // auth credentials or arbitrary customer profile columns.
                ->with('customerProfile:user_id,account_type,phone,country,company_name,service_interest')
                ->when($statusFilter === 'verified', static fn ($query) => $query->whereNotNull('email_verified_at'))
                ->when($statusFilter === 'unverified', static fn ($query) => $query->whereNull('email_verified_at'))
                ->when($userFilter !== '', static function ($query) use ($userFilter): void {
                    $escaped = addcslashes($userFilter, '%_\\');
                    $query->where(static function ($q) use ($escaped): void {
                        $q->where('name', 'like', '%'.$escaped.'%')
                            ->orWhere('email', 'like', '%'.$escaped.'%')
                            ->orWhereHas('customerProfile', static function ($profile) use ($escaped): void {
                                $profile->where('company_name', 'like', '%'.$escaped.'%')
                                    ->orWhere('phone', 'like', '%'.$escaped.'%')
                                    ->orWhere('country', 'like', '%'.$escaped.'%');
                            });
                    });
                })
                ->orderByDesc('id')
                ->paginate(15, ['*'], 'users_page')
                ->withQueryString();

            $organizations = Organization::query()
                ->select(['id', 'name', 'created_at'])
                ->withCount('memberships')
                ->when($orgFilter !== '', static function ($query) use ($orgFilter): void {
                    $query->where('name', 'like', '%'.addcslashes($orgFilter, '%_\\').'%');
                })
                ->orderByDesc('created_at')
                ->orderBy('id')
                ->paginate(15, ['*'], 'orgs_page')
                ->withQueryString();

            return Inertia::render('operator-directory', [
                'filters' => [
                    'users_q' => $userFilter,
                    'users_status' => $statusFilter,
                    'orgs_q' => $orgFilter,
                ],
                'users' => $users,
                'organizations' => $organizations,
                'read_only' => false,
            ]);
        })->name('directory.index');

        Route::patch('directory/users/{user}/contact', function (
            Request $request,
            User $user,
            PlatformOwnerAccess $access,
            OwnerDirectoryAccountActions $actions,
        ) {
            $actor = $request->user();
            abort_unless($actor instanceof User, 401);
            $access->require($actor);

            // Validate the displayed value, not an untrimmed string whose
            // whitespace would be removed only after the length check.
            $requestedName = $request->input('name');
            if (is_string($requestedName)) {
                $request->merge(['name' => trim($requestedName)]);
            }

            $values = $request->validate([
                'name' => ['required', 'string', 'min:2', 'max:120'],
                // Existing profile columns are NOT NULL: an explicit blank
                // must report validation error, not silently keep old data.
                'phone' => ['sometimes', 'required', 'string', 'min:1', 'max:32'],
                'country' => ['sometimes', 'required', 'string', 'min:1', 'max:80'],
                'company_name' => ['sometimes', 'nullable', 'string', 'max:160'],
                'service_interest' => ['sometimes', 'nullable', 'in:software,cloud,remote_access,calibration,cinema,other'],
            ]);
            try {
                $actions->updateContact((int) $user->id, (int) $actor->id, $values);
            } catch (RuntimeException) {
                throw ValidationException::withMessages([
                    'user' => 'This account is protected and cannot be edited here.',
                ]);
            }

            return redirect()->route('operator.directory.index');
        })->middleware('throttle:8,1')->name('directory.user-contact');

        Route::post('directory/users/{user}/delete', function (
            Request $request,
            User $user,
            PlatformOwnerAccess $access,
            OwnerDirectoryAccountActions $actions,
        ) {
            $actor = $request->user();
            abort_unless($actor instanceof User, 401);
            $access->require($actor);
            $values = $request->validate([
                'confirmation' => ['required', 'string', 'max:80'],
            ]);
            abort_unless(
                hash_equals('DELETE_USER_'.(int) $user->id, (string) $values['confirmation']),
                422,
            );
            try {
                $actions->deleteCustomerAndSignupData((int) $user->id, (int) $actor->id);
            } catch (RuntimeException) {
                throw ValidationException::withMessages([
                    'user' => 'Deletion blocked: this customer has a shared organization or linked payment, license, identity or audit records. No data was removed.',
                ]);
            }

            return redirect()->route('operator.directory.index');
        })->middleware('throttle:2,1')->name('directory.user-delete');
    });
