<?php

declare(strict_types=1);

use App\Services\Licensing\OmniDesk\OmniDeskActivationQueryService;
use App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer;
use App\Services\Licensing\OmniDesk\OmniDeskApiPrincipal;
use App\Services\Licensing\OmniDesk\OmniDeskProtectedLeaseService;
use App\Services\Licensing\OmniDesk\OmniDeskRenewalChallengeStore;
use App\Services\Licensing\OmniDesk\OmniDeskSigner;
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
        'OMNIDESK_RENEWAL_CHALLENGE_DENIED' => ['ACTIVATION_REVOKED', 404],
        'OMNIDESK_REASON_REQUIRED', 'INVALID_REQUEST' => ['INVALID_REQUEST', 422],
        'OMNIDESK_ACTIVATION_PROOF_INVALID' => ['FORBIDDEN', 403],
        'OMNIDESK_ACTIVATION_CONFLICT' => ['ACTIVATION_CONFLICT', 409],
        'OMNIDESK_REPLAY_DETECTED', 'OMNIDESK_LEASE_SEQUENCE_INVALID' => ['REPLAY_DETECTED', 409],
        'OMNIDESK_LICENSE_INACTIVE', 'OMNIDESK_ENTITLEMENT_INACTIVE' => ['ENTITLEMENT_INACTIVE', 403],
        'OMNIDESK_SIGNER_UNAVAILABLE' => ['ISSUANCE_NOT_CONFIGURED', 503],
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
    // These routes remain fail-closed in production until the owner-protected
    // signing service is explicitly bound to OmniDeskSigner. A configured
    // authorizer alone can never issue a lease or a mock signature.
    Route::post('activations', function (Request $request) use ($omnideskPrincipal, $omnideskError) {
        if (strlen($request->getContent()) > 2048) {
            return response()->json(['error' => 'INVALID_REQUEST'], 413)
                ->header('Cache-Control', 'no-store, private');
        }

        try {
            $principal = $omnideskPrincipal($request);
            if (! $principal->canManage) {
                throw new DomainException('OMNIDESK_FORBIDDEN');
            }
            if (! app()->bound(OmniDeskSigner::class)) {
                return response()->json(['error' => 'ISSUANCE_NOT_CONFIGURED'], 503)
                    ->header('Cache-Control', 'no-store, private');
            }

            $key = $request->header('Idempotency-Key');
            if (! is_string($key)) {
                throw new DomainException('INVALID_REQUEST');
            }
            $issued = app(OmniDeskProtectedLeaseService::class)->activate(
                $request->all(),
                $key,
                $principal,
                app(OmniDeskSigner::class),
            );

            return response()->json($issued)->header('Cache-Control', 'no-store, private');
        } catch (Throwable $error) {
            return $omnideskError($error);
        }
    })->middleware('throttle:12,1');

    Route::post('leases/renew', function (Request $request) use ($omnideskPrincipal, $omnideskError) {
        if (strlen($request->getContent()) > 2048) {
            return response()->json(['error' => 'INVALID_REQUEST'], 413)
                ->header('Cache-Control', 'no-store, private');
        }

        try {
            $principal = $omnideskPrincipal($request);
            if (! $principal->canManage) {
                throw new DomainException('OMNIDESK_FORBIDDEN');
            }
            if (! app()->bound(OmniDeskSigner::class)) {
                return response()->json(['error' => 'ISSUANCE_NOT_CONFIGURED'], 503)
                    ->header('Cache-Control', 'no-store, private');
            }
            $issued = app(OmniDeskProtectedLeaseService::class)->renew(
                $request->all(),
                $principal,
                app(OmniDeskSigner::class),
            );

            return response()->json($issued)->header('Cache-Control', 'no-store, private');
        } catch (Throwable $error) {
            return $omnideskError($error);
        }
    })->middleware('throttle:12,1');

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

    // Strictly owner-managed challenge issuance. Device-only authorization is
    // a separate, unimplemented integration, so never accept an untrusted
    // client-selected tenant or device identity for this endpoint.
    Route::post('activations/{activation_id}/renewal-challenge', function (
        Request $request,
        string $activation_id,
        OmniDeskRenewalChallengeStore $store,
    ) use ($omnideskPrincipal, $omnideskError) {
        try {
            $principal = $omnideskPrincipal($request);
            if (! $principal->canManage) {
                throw new DomainException('OMNIDESK_FORBIDDEN');
            }
            if (strlen($request->getContent()) > 128 || $request->all() !== []) {
                return response()->json(['error' => 'INVALID_REQUEST'], 422)
                    ->header('Cache-Control', 'no-store, private');
            }

            $issued = $store->issue($activation_id, $principal->organizationId);

            return response()->json([
                'activation_id' => $activation_id,
                'proof_scheme' => 'KMJ-OMNIDESK-RENEW-v1',
                'server_challenge' => $issued['server_challenge'],
                'expires_in' => $issued['expires_in'],
            ])->header('Cache-Control', 'no-store, private');
        } catch (Throwable $error) {
            return $omnideskError($error);
        }
    })->whereUuid('activation_id')->middleware('throttle:12,1');

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
