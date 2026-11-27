<?php

use App\Models\User;
use App\Services\Commerce\ProductSignups;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

// A signed-in, verified customer asks for a trial or pre-registers. The server
// decides what (if anything) is granted; the browser only names the product.
Route::post('product-signups', function (Request $request, ProductSignups $signups) {
    $user = $request->user();
    abort_unless($user instanceof User, 401);

    $data = $request->validate(['product' => ['required', 'string', 'max:96']]);

    abort_unless($signups->available(), 503, 'Sign-up is not ready yet.');
    abort_unless($signups->record($user, $data['product']), 404);

    return redirect()->route('dashboard');
})->middleware(['auth', 'verified', 'throttle:10,1'])->name('product-signups.store');
