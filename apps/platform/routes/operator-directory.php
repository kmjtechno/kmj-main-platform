<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
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
                'orgs_q' => ['sometimes', 'nullable', 'string', 'max:80'],
                'users_page' => ['sometimes', 'integer', 'min:1', 'max:100000'],
                'orgs_page' => ['sometimes', 'integer', 'min:1', 'max:100000'],
            ]);

            $userFilter = trim((string) ($filters['users_q'] ?? ''));
            $orgFilter = trim((string) ($filters['orgs_q'] ?? ''));

            // Read-only discovery with explicit columns; never serialize the
            // authentication model (password, passkeys, tokens or recovery).
            $users = User::query()
                ->select(['id', 'name', 'email', 'email_verified_at', 'created_at', 'is_platform_owner'])
                // Explicit allowlist of business/contact fields: never expose
                // auth credentials or arbitrary customer profile columns.
                ->with('customerProfile:user_id,account_type,phone,country,company_name,service_interest')
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
                    'orgs_q' => $orgFilter,
                ],
                'users' => $users,
                'organizations' => $organizations,
                'read_only' => true,
            ]);
        })->name('directory.index');
    });
