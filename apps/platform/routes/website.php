<?php

use App\Http\Controllers\OwnerWebsiteController;
use Illuminate\Support\Facades\Route;

Route::get('team', [OwnerWebsiteController::class, 'team'])->name('team');
Route::get('team-photo/{asset}', [OwnerWebsiteController::class, 'showPhoto'])->name('team.photo');

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/website')
    ->name('operator.website.')
    ->group(function (): void {
        Route::get('/', [OwnerWebsiteController::class, 'index'])->name('index');
        Route::put('site', [OwnerWebsiteController::class, 'updateSite'])->middleware('throttle:30,1')->name('site');
        Route::put('team', [OwnerWebsiteController::class, 'updateTeam'])->middleware('throttle:30,1')->name('team');
        Route::post('team/photo', [OwnerWebsiteController::class, 'uploadPhoto'])->middleware('throttle:20,1')->name('photo');
    });
