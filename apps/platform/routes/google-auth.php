<?php

use App\Http\Controllers\Auth\CompleteProfileController;
use App\Http\Controllers\Auth\GoogleAuthController;
use Illuminate\Support\Facades\Route;

Route::middleware(['guest', 'throttle:20,1'])->group(function () {
    Route::get('auth/google/redirect', [GoogleAuthController::class, 'redirect'])->name('auth.google.redirect');
    Route::get('auth/google/callback', [GoogleAuthController::class, 'callback'])->name('auth.google.callback');
});

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('onboarding/profile', [CompleteProfileController::class, 'show'])->name('onboarding.profile.show');
    Route::post('onboarding/profile', [CompleteProfileController::class, 'store'])
        ->name('onboarding.profile.store')->middleware('throttle:20,1');
});
