<?php

declare(strict_types=1);

use App\Services\Licensing\OmniDesk\OmniDeskActivationQueryService;
use App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer;
use App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Validation\ValidationException;

$omnideskPrincipal = static function (Request $request): OmniDeskApiPrincipal {
    if (! app()->bound(OmniDeskApiAuthorizer::class)) {
        throw new RuntimeException('OMNIDESK_AUTHORIZER_UNAVAILABLE');
    }

    return app(OmniDeskApiAuthorizer::class)->authorize($request);
};

$omnideskError = static function (Throwable $error) {
    if ($error instanceof RuntimeException
        && $error->getMessage() === 'OMNIDESK_AUTHORIZER_UNAVAILABLE') {
        return response()->json(['error' => 'SERVER_UNAVAILABLE'], 503)
            ->header('Cache-Control', 'no-store');
    }

    if ($error instanceof ValidationException) {
        return response()->json(['error' => 'INVALID_REQUEST'], 422)
            ->header('Cache-Control', 'no-store');
    }

    if (($error instanceof DomainException) === false) {
        return response()->json(['error' => 'SERVER_UNAVAILABLE'], 503)
            ->header('Cache-Control', 'no-store');
    }

    [$code, $status] = match ($error->getMessage()) {
        'OMNIDESK_UNAUTHENTICATED' => ['UNAUTHENTICATED', 401],
        'OMNIDESK_FORBIDDEN' => ['FORBIDDEN', 403],
        'OMNIDESK_ACTIVATION_NOT_FOUND' => ['ACTIVATION_REVOKED', 404],
        'OMNIDESK_REASON_REQUIRED' => ['INVALID_REQUEST', 422],
        'OMNIDESK_PRODUCT_NOT_FOUND' => ['SERVER_UNAVAILABLE', 503],
        default => ['SERVER_UNAVAILABLE', 503],
    };

    return response()->json(['error' => $code], $status)
        ->header('Cache-Control', 'no-store');
};

Route::prefix('v1/licensing/omnidesk')->group(function () use (
    $omnideskPrincipal,
    $omnideskError,
): void {
    Route::get('activations/{activation_id}/status', function (
        Request $request,
        string $activation_id,
        OmniDeskActivationQueryService $service,
    ) use ($omnideskPrincipal, $omnideskError) {
        try {
            $principal = $omnideskPrincipal($request);

            return response()->json(
                $service->status($activation_id, $principal),
            )->header('Cache-Control', 'no-store');
        } catch (Throwable $error) {
            return $omnideskError($error);
        }
    })->whereUuid('activation_id')->middleware('throttle:60,1');

    Route::get('entitlements/current', function (
        Request $request,
        OmniDeskActivationQueryService $service,
    ) use ($omnideskPrincipal, $omnideskError) {
        try {
            $principal = $omnideskPrincipal($request);

            return response()->json(
                $service->currentEntitlements($principal),
            )->header('Cache-Control', 'no-store');
        } catch (Throwable $error) {
            return $omnideskError($error);
        }
    })->middleware('throttle:60,1');

    Route::post('activations/{activation_id}/deactivate', function (
        Request $request,
        string $activation_id,
        OmniDeskActivationQueryService $service,
    ) use ($omnideskPrincipal, $omnideskError) {
        if (strlen($request->getContent()) > 2048) {
            return response()->json(['error' => 'INVALID_REQUEST'], 413)
                ->header('Cache-Control', 'no-store');
        }

        try {
            $principal = $omnideskPrincipal($request);
            $data = $request->validate([
                'reason' => ['required', 'string', 'min:3', 'max:500'],
            ]);

            return response()->json(
                $service->deactivate($activation_id, $principal, $data['reason']),
            )->header('Cache-Control', 'no-store');
        } catch (Throwable $error) {
            return $omnideskError($error);
        }
    })->whereUuid('activation_id')->middleware('throttle:20,1');
});
