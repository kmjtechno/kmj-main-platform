<?php

use App\Http\Controllers\OwnerProductStudioController;
use App\Models\User;
use App\Services\Commerce\AdminProductManager;
use App\Services\PlatformOwnerAccess;
use App\Services\ProductStudio\FreeCloudProductDraftGenerator;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Validation\ValidationException;
use Inertia\Inertia;
use KMJ\MainPlatform\Catalog\Models\Product;

Route::get('product-artwork/{asset}', [OwnerProductStudioController::class, 'showArtwork'])->name('product-artwork.show');

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/products')
    ->name('operator.products.')
    ->group(function (): void {
        Route::get('/', function (Request $request, PlatformOwnerAccess $access, FreeCloudProductDraftGenerator $generator) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            return Inertia::render('operator-products', [
                'generation' => $generator->configuration(),
                'products' => Product::query()
                    ->orderBy('sort_order')
                    ->orderBy('name')
                    ->get([
                        'id', 'slug', 'name', 'status', 'lifecycle', 'category',
                        'is_public', 'sort_order', 'image_path', 'summary',
                        'purchase_enabled', 'licensing_enabled', 'content',
                    ]),
            ]);
        })->name('index');

        Route::post('draft', [OwnerProductStudioController::class, 'draft'])->middleware('throttle:6,1')->name('draft');
        Route::post('media', [OwnerProductStudioController::class, 'media'])->middleware('throttle:6,1')->name('media');

        Route::post('/', function (Request $request, PlatformOwnerAccess $access, AdminProductManager $manager) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            try {
                $manager->create($request->validate(AdminProductManager::rules()));
            } catch (DomainException $exception) {
                throw ValidationException::withMessages(['purchase_enabled' => $exception->getMessage()]);
            }

            return back()->with('success', 'Product created.');
        })->name('store');

        Route::put('{product}', function (Request $request, Product $product, PlatformOwnerAccess $access, AdminProductManager $manager) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            try {
                $manager->update($product, $request->validate(AdminProductManager::rules($product, true)));
            } catch (DomainException $exception) {
                throw ValidationException::withMessages(['purchase_enabled' => $exception->getMessage()]);
            }

            return back()->with('success', 'Product updated.');
        })->name('update');

        Route::post('reorder', function (Request $request, PlatformOwnerAccess $access, AdminProductManager $manager) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            $data = $request->validate(['ids' => ['required', 'array', 'min:1'], 'ids.*' => ['required', 'uuid', 'distinct']]);
            try {
                $manager->reorder($data['ids']);
            } catch (DomainException $exception) {
                throw ValidationException::withMessages(['ids' => $exception->getMessage()]);
            }

            return back()->with('success', 'Product order updated.');
        })->name('reorder');
    });
