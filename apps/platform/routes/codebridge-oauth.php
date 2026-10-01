<?php

use App\Services\CodeBridge\OAuth\OAuthError;
use App\Services\CodeBridge\OAuth\OAuthServer;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Str;
use Inertia\Inertia;

/*
| CodeBridge OAuth 2.1 authorization server. Every endpoint returns 404 unless
| CODEBRIDGE_OAUTH_ENABLED is set and the signing key and resource are
| configured, so this ships dark until operators provision it.
*/

$noStore = ['Cache-Control' => 'no-store', 'Pragma' => 'no-cache'];
$oauthError = fn (OAuthError $e): JsonResponse => response()->json(['error' => $e->error], $e->status === 302 ? 400 : $e->status, $noStore);

Route::get('.well-known/oauth-authorization-server', function (OAuthServer $server) {
    abort_unless($server->enabled(), 404);

    return response()->json($server->metadata());
})->name('codebridge.oauth.metadata');

Route::get('oauth/jwks.json', function (OAuthServer $server) {
    abort_unless($server->enabled(), 404);

    return response()->json($server->jwks());
})->name('codebridge.oauth.jwks');

Route::post('oauth/register', function (Request $request, OAuthServer $server) use ($noStore, $oauthError) {
    abort_unless($server->enabled(), 404);
    if (strlen($request->getContent()) > 8192 || ! $request->isJson()) {
        return response()->json(['error' => 'invalid_client_metadata'], 400, $noStore);
    }
    try {
        return response()->json($server->register($request->json()->all()), 201, $noStore);
    } catch (OAuthError $e) {
        return $oauthError($e);
    }
})->middleware('throttle:20,1')->name('codebridge.oauth.register');

Route::post('oauth/token', function (Request $request, OAuthServer $server) use ($noStore, $oauthError) {
    abort_unless($server->enabled(), 404);
    if (strlen($request->getContent()) > 8192) {
        return response()->json(['error' => 'invalid_request'], 400, $noStore);
    }
    try {
        return response()->json($server->token($request->post()), 200, $noStore);
    } catch (OAuthError $e) {
        return $oauthError($e);
    }
})->middleware('throttle:60,1')->name('codebridge.oauth.token');

Route::middleware(['auth', 'verified'])->group(function () use ($noStore): void {
    Route::get('oauth/authorize', function (Request $request, OAuthServer $server) use ($noStore) {
        abort_unless($server->enabled(), 404);
        try {
            $validated = $server->validateAuthorization($request->query());
        } catch (OAuthError $e) {
            if ($e->status === 302 && $e->redirectUri !== null) {
                $query = http_build_query(array_filter(['error' => $e->error, 'state' => $e->state, 'iss' => $server->issuer()], fn ($v) => $v !== null), '', '&', PHP_QUERY_RFC3986);

                return redirect()->away($e->redirectUri.(str_contains($e->redirectUri, '?') ? '&' : '?').$query);
            }

            return response('The authorization request is invalid ('.$e->error.').', 400, $noStore + ['Content-Type' => 'text/plain']);
        }
        $id = Str::random(40);
        $request->session()->put('codebridge_oauth.'.$id, $validated);

        return Inertia::render('auth/oauth-authorize', [
            'requestId' => $id,
            'clientName' => $validated['client_name'],
            'redirectHost' => $validated['redirect_host'],
            'scopes' => $validated['scopes'],
        ]);
    })->name('codebridge.oauth.authorize');

    Route::post('oauth/authorize', function (Request $request, OAuthServer $server) {
        abort_unless($server->enabled(), 404);
        $data = $request->validate([
            'request_id' => ['required', 'string', 'size:40'],
            'decision' => ['required', 'in:approve,deny'],
        ]);
        $pending = $request->session()->pull('codebridge_oauth.'.$data['request_id']);
        abort_unless(is_array($pending), 400, 'This authorization request expired. Start again from your AI app.');
        /** @var array{client_id:string,client_name:string,redirect_uri:string,redirect_host:string,scopes:list<string>,state:?string,code_challenge:string,resource:string} $pending */

        $target = $data['decision'] === 'approve'
            ? $server->approve($pending, (int) $request->user()->getAuthIdentifier())
            : $server->deny($pending);

        return Inertia::location($target);
    })->name('codebridge.oauth.decide');
});
