<?php

declare(strict_types=1);

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
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
                ->when($userFilter !== '', static function ($query) use ($userFilter): void {
                    $escaped = addcslashes($userFilter, '%_\\');
                    $query->where(static function ($q) use ($escaped): void {
                        $q->where('name', 'like', '%'.$escaped.'%')
                            ->orWhere('email', 'like', '%'.$escaped.'%');
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
                'read_only' => false,
            ]);
        })->name('directory.index');

        // Owner-only profile editing. Email, verification, passwords, roles,
        // membership and license state cannot be modified by these endpoints.
        Route::patch('directory/users/{user}', function (
            Request $request,
            string $user,
            PlatformOwnerAccess $access,
        ) {
            $actor = $request->user();
            abort_unless($actor instanceof User, 401);
            $access->require($actor);

            $validated = $request->validate([
                'name' => ['required', 'string', 'min:2', 'max:120'],
            ]);

            DB::transaction(function () use ($actor, $user, $validated): void {
                $customer = User::query()->findOrFail($user);
                $customer->update(['name' => trim($validated['name'])]);
                OperatorActionAudit::query()->create([
                    'actor_user_id' => $actor->id,
                    'action' => 'customer.profile_name_updated',
                    'outcome' => 'success',
                    'metadata' => ['customer_user_id' => $customer->id, 'fields' => ['name']],
                ]);
            });

            return back()->with('success', 'Customer display name updated.');
        })->whereNumber('user')->middleware('throttle:10,1')->name('directory.users.update');

        Route::patch('directory/organizations/{organization}', function (
            Request $request,
            string $organization,
            PlatformOwnerAccess $access,
        ) {
            $actor = $request->user();
            abort_unless($actor instanceof User, 401);
            $access->require($actor);

            $validated = $request->validate([
                'name' => ['required', 'string', 'min:2', 'max:160'],
            ]);

            DB::transaction(function () use ($actor, $organization, $validated): void {
                $customer = Organization::query()->findOrFail($organization);
                $customer->update(['name' => trim($validated['name'])]);
                OperatorActionAudit::query()->create([
                    'actor_user_id' => $actor->id,
                    'action' => 'customer.organization_name_updated',
                    'outcome' => 'success',
                    'metadata' => ['organization_id' => $customer->getKey(), 'fields' => ['name']],
                ]);
            });

            return back()->with('success', 'Customer organization updated.');
        })->whereUuid('organization')->middleware('throttle:10,1')->name('directory.organizations.update');
    });
