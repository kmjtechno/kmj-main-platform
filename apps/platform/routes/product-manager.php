<?php

use App\Models\User;
use App\Services\Commerce\AdminProductManager;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use KMJ\MainPlatform\Catalog\Models\Product;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/products')
    ->name('operator.products.')
    ->group(function (): void {
        Route::post('/', function (Request $request, PlatformOwnerAccess $access, AdminProductManager $manager) {
            $user = $request->user(); abort_unless($user instanceof User, 401); $access->require($user);
            $manager->create($request->validate(AdminProductManager::rules()));
            return back()->with('success', 'Product created.');
        })->name('store');

        Route::put('{product}', function (Request $request, Product $product, PlatformOwnerAccess $access, AdminProductManager $manager) {
            $user = $request->user(); abort_unless($user instanceof User, 401); $access->require($user);
            $manager->update($product, $request->validate(AdminProductManager::rules($product, true)));
            return back()->with('success', 'Product updated.');
        })->name('update');

        Route::post('reorder', function (Request $request, PlatformOwnerAccess $access, AdminProductManager $manager) {
            $user = $request->user(); abort_unless($user instanceof User, 401); $access->require($user);
            $data = $request->validate(['ids' => ['required','array','min:1'], 'ids.*' => ['required','uuid','distinct']]);
            $manager->reorder($data['ids']);
            return back()->with('success', 'Product order updated.');
        })->name('reorder');
    });
