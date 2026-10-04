<?php

use App\Models\User;
use App\Services\CodeBridge\OAuth\OAuthError;
use App\Services\CodeBridge\OAuth\OAuthServer;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
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

Route::get('.well-known/openid-configuration', function (OAuthServer $server) {
    abort_unless($server->enabled(), 404);

    return response()->json($server->metadata());
})->name('codebridge.oauth.openid');

Route::get('.well-known/oauth-protected-resource', function (OAuthServer $server) {
    abort_unless($server->enabled(), 404);

    return response()->json([
        'resource' => $server->resource(),
        'authorization_servers' => [$server->issuer()],
        'scopes_supported' => [
            'codebridge:read',
            'codebridge:write',
            'codebridge:execute',
        ],
    ]);
})->name('codebridge.oauth.resource');

Route::get('.well-known/oauth-protected-resource/mcp', function (OAuthServer $server) {
    abort_unless($server->enabled(), 404);

    return response()->json([
        'resource' => $server->resource(),
        'authorization_servers' => [$server->issuer()],
        'scopes_supported' => [
            'codebridge:read',
            'codebridge:write',
            'codebridge:execute',
        ],
    ]);
})->name('codebridge.oauth.resource.mcp');

Route::post('mcp', function (Request $request, OAuthServer $server) {
    abort_unless($server->enabled(), 404);
    if (strlen($request->getContent()) > 1048576) {
        abort(413);
    }

    $upstream = rtrim((string) config('services.codebridge_gateway.url'), '/');
    abort_unless(
        str_starts_with($upstream, 'https://') || str_starts_with($upstream, 'http://127.0.0.1:'),
        503,
    );

    $headers = [
        'Accept' => (string) $request->header('Accept', 'application/json, text/event-stream'),
        'Content-Type' => (string) $request->header('Content-Type', 'application/json'),
    ];
    foreach (['Authorization', 'MCP-Protocol-Version'] as $name) {
        $value = $request->header($name);
        if (is_string($value) && $value !== '') {
            $headers[$name] = $value;
        }
    }

    try {
        $upstreamResponse = Http::timeout(25)
            ->connectTimeout(5)
            ->withoutRedirecting()
            ->withHeaders($headers)
            ->withBody($request->getContent(), $headers['Content-Type'])
            ->post($upstream.'/mcp');
    } catch (Throwable) {
        return response()->json(['error' => 'CODEBRIDGE_GATEWAY_UNAVAILABLE'], 503)
            ->header('Cache-Control', 'no-store');
    }

    $responseHeaders = ['Cache-Control' => 'no-store'];
    foreach (['Content-Type', 'WWW-Authenticate'] as $name) {
        $value = $upstreamResponse->header($name);
        if ($value !== '') {
            $responseHeaders[$name] = $value;
        }
    }

    return response($upstreamResponse->body(), $upstreamResponse->status(), $responseHeaders);
})->middleware('throttle:240,1')->name('codebridge.mcp');

Route::post('agent/{operation}', function (Request $request, OAuthServer $server, string $operation) {
    abort_unless($server->enabled(), 404);
    abort_unless(in_array($operation, ['health', 'poll', 'result'], true), 404);
    if (strlen($request->getContent()) > 1048576) {
        abort(413);
    }

    $upstream = rtrim((string) config('services.codebridge_gateway.url'), '/');
    abort_unless(
        str_starts_with($upstream, 'https://') || str_starts_with($upstream, 'http://127.0.0.1:'),
        503,
    );

    $headers = [
        'Accept' => (string) $request->header('Accept', 'application/json'),
        'Content-Type' => (string) $request->header('Content-Type', 'application/json'),
    ];
    $authorization = $request->header('Authorization');
    if (is_string($authorization) && $authorization !== '') {
        $headers['Authorization'] = $authorization;
    }

    try {
        $upstreamResponse = Http::timeout(70)
            ->connectTimeout(5)
            ->withoutRedirecting()
            ->withHeaders($headers)
            ->withBody($request->getContent(), $headers['Content-Type'])
            ->post($upstream.'/agent/'.$operation);
    } catch (Throwable) {
        return response()->json(['error' => 'CODEBRIDGE_GATEWAY_UNAVAILABLE'], 503)
            ->header('Cache-Control', 'no-store');
    }

    $responseHeaders = ['Cache-Control' => 'no-store'];
    $contentType = $upstreamResponse->header('Content-Type');
    if ($contentType !== '') {
        $responseHeaders['Content-Type'] = $contentType;
    }

    return response($upstreamResponse->body(), $upstreamResponse->status(), $responseHeaders);
})->where('operation', 'health|poll|result')
    ->middleware('throttle:240,1')
    ->name('codebridge.agent.compat');

Route::get('oauth/jwks.json', function (OAuthServer $server) {
    abort_unless($server->enabled(), 404);

    return response()->json($server->jwks());
})->name('codebridge.oauth.jwks');

Route::get('oauth/userinfo', function (Request $request, OAuthServer $server) use ($noStore) {
    abort_unless($server->enabled(), 404);

    $token = $request->bearerToken();
    $claims = is_string($token) ? $server->verifyAccessToken($token) : null;
    if (! is_array($claims) || ! preg_match('/\Akmj-user:([1-9][0-9]*)\z/D', (string) ($claims['sub'] ?? ''), $match)) {
        return response()->json(['error' => 'invalid_token'], 401, $noStore)
            ->header('WWW-Authenticate', 'Bearer error="invalid_token"');
    }

    if (! in_array('openid', $claims['scopes'] ?? [], true)) {
        return response()->json(['error' => 'insufficient_scope'], 403, $noStore)
            ->header('WWW-Authenticate', 'Bearer error="insufficient_scope", scope="openid"');
    }

    $user = User::query()->find((int) $match[1]);
    if (! $user instanceof User) {
        return response()->json(['error' => 'invalid_token'], 401, $noStore)
            ->header('WWW-Authenticate', 'Bearer error="invalid_token"');
    }

    return response()->json([
        'sub' => (string) $claims['sub'],
        'email' => (string) $user->email,
        'email_verified' => $user->email_verified_at !== null,
        'name' => (string) $user->name,
    ], 200, $noStore);
})->name('codebridge.oauth.userinfo');

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
