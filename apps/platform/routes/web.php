<?php

use App\Http\Controllers\CodeBridgeOAuthLinkController;
use App\Models\LicenseAuditEvent;
use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\CodeBridge\OAuth\OAuthServer;
use App\Services\Commerce\DesktopCommanderCommercialPolicy;
use App\Services\Commerce\KmjProductCatalog;
use App\Services\Commerce\PublicProductCatalog;
use App\Services\Licensing\CodeBridge\CodeBridgeDevicePairingService;
use App\Services\Licensing\LicenseAuditRecorder;
use App\Services\Licensing\SandboxLicenseLifecycle;
use App\Services\PlatformOwnerAccess;
use App\Services\Releases\CustomerReleaseAccess;
use App\Services\Releases\ReleaseArtifactDelivery;
use DateTimeImmutable as ImmutableDateTime;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Models\Organization;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;
use KMJ\MainPlatform\Releases\Models\ReleaseArtifact;

Route::get('api/public/commander/bootstrap', function (DesktopCommanderCommercialPolicy $policy) {
    return response()
        ->json($policy->publicBootstrap())
        ->header('Cache-Control', 'public, max-age=3600, stale-while-revalidate=86400')
        ->header('Access-Control-Allow-Origin', '*');
})->name('commander.bootstrap');

Route::get('install', function () {
    $script = <<<'BASH'
#!/usr/bin/env bash
set -euo pipefail

CODEBRIDGE_RELEASE_REF='ff8a64273ce46e6ddcae1c62e054917be8572b4e'
CODEBRIDGE_INSTALLER_URL='https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/ff8a64273ce46e6ddcae1c62e054917be8572b4e/scripts/install-vps.sh'

tmp="$(mktemp)"
cleanup() {
  rm -f "$tmp"
}
trap cleanup EXIT

curl -fsSL --proto '=https' --tlsv1.2 "$CODEBRIDGE_INSTALLER_URL" -o "$tmp"
export CODEBRIDGE_REF="$CODEBRIDGE_RELEASE_REF"
bash "$tmp" "$@"
BASH;

    return response($script."\n", 200, [
        'Content-Type' => 'text/x-shellscript; charset=UTF-8',
        'Cache-Control' => 'public, max-age=300',
        'X-Content-Type-Options' => 'nosniff',
    ]);
})->name('codebridge.install');

Route::get('install-chatgpt-desktop.ps1', function () {
    $script = <<<'POWERSHELL'
$ErrorActionPreference = 'Stop'

Write-Host 'KMJ CodeBridge - ChatGPT Desktop setup' -ForegroundColor Cyan

$marketplace = 'kmj-techno'
$repo = 'kmjtechno/kmj-codebridge'
$pluginName = 'kmj-codebridge'
$codex = Get-Command codex -ErrorAction SilentlyContinue

if ($codex) {
    $existing = & codex plugin marketplace list 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to read ChatGPT plugin marketplaces.'
    }

    if ($existing -match [regex]::Escape($marketplace)) {
        Write-Host 'Refreshing existing KMJ TECHNO marketplace...'
        & codex plugin marketplace upgrade $marketplace
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to refresh the KMJ TECHNO marketplace.'
        }
    } else {
        Write-Host 'Adding KMJ TECHNO marketplace...'
        & codex plugin marketplace add $repo --ref main
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to add the KMJ TECHNO marketplace.'
        }
    }
} else {
    Write-Host 'Codex CLI was not found; using the ChatGPT Desktop personal-marketplace fallback.'

    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw 'Node.js is required by the KMJ CodeBridge Desktop bridge and was not found in PATH.'
    }

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('kmj-codebridge-' + [guid]::NewGuid().ToString('N'))
    $zipPath = Join-Path $tempRoot 'kmj-codebridge.zip'
    $extractPath = Join-Path $tempRoot 'src'
    $pluginDir = Join-Path $HOME '.codex\plugins\kmj-codebridge'
    $marketplacePath = Join-Path $HOME '.agents\plugins\marketplace.json'

    try {
        New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
        New-Item -ItemType Directory -Force -Path $extractPath | Out-Null

        Write-Host 'Downloading the public KMJ CodeBridge repository...'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/kmjtechno/kmj-codebridge/archive/refs/heads/main.zip' -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

        $repoRoot = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
        if (-not $repoRoot) {
            throw 'Downloaded CodeBridge archive did not contain a repository root.'
        }

        $sourcePlugin = Join-Path $repoRoot.FullName 'plugin'
        if (-not (Test-Path (Join-Path $sourcePlugin 'plugin.json'))) {
            throw 'Downloaded CodeBridge archive did not contain plugin/plugin.json.'
        }

        New-Item -ItemType Directory -Force -Path (Split-Path $pluginDir -Parent) | Out-Null
        if (Test-Path $pluginDir) {
            Remove-Item -Recurse -Force $pluginDir
        }
        Copy-Item -Recurse -Force $sourcePlugin $pluginDir

        New-Item -ItemType Directory -Force -Path (Split-Path $marketplacePath -Parent) | Out-Null

        if (Test-Path $marketplacePath) {
            Copy-Item $marketplacePath ($marketplacePath + '.before-kmj-codebridge') -Force
            try {
                $catalog = Get-Content -Raw $marketplacePath | ConvertFrom-Json
            } catch {
                throw 'Existing personal plugin marketplace JSON is invalid. A backup was preserved next to it.'
            }
        } else {
            $catalog = [pscustomobject]@{
                name = 'personal'
                interface = [pscustomobject]@{ displayName = 'Personal' }
                plugins = @()
            }
        }

        if (-not $catalog.PSObject.Properties['name']) {
            $catalog | Add-Member -NotePropertyName name -NotePropertyValue 'personal'
        }
        if (-not $catalog.PSObject.Properties['interface']) {
            $catalog | Add-Member -NotePropertyName interface -NotePropertyValue ([pscustomobject]@{ displayName = 'Personal' })
        }
        if (-not $catalog.PSObject.Properties['plugins']) {
            $catalog | Add-Member -NotePropertyName plugins -NotePropertyValue @()
        }

        $keptPlugins = @($catalog.plugins | Where-Object { $_.name -ne $pluginName })
        $kmjPlugin = [pscustomobject]@{
            name = $pluginName
            source = [pscustomobject]@{
                source = 'local'
                path = './.codex/plugins/kmj-codebridge'
            }
            policy = [pscustomobject]@{
                installation = 'INSTALLED_BY_DEFAULT'
                authentication = 'ON_INSTALL'
            }
            category = 'Developer Tools'
        }
        $catalog.plugins = @($keptPlugins) + @($kmjPlugin)
        $catalog | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $marketplacePath
    } finally {
        if (Test-Path $tempRoot) {
            Remove-Item -Recurse -Force $tempRoot
        }
    }
}

Write-Host ''
Write-Host 'KMJ CodeBridge marketplace has been configured.' -ForegroundColor Green
Write-Host 'Fully quit and reopen ChatGPT Desktop, then open Plugins > KMJ TECHNO.'
Write-Host 'Install or enable KMJ CodeBridge if prompted and connect the existing app.'
Write-Host 'Complete any browser authorization requested by ChatGPT or KMJ.'
Write-Host 'This installer does not bypass plugin installation, access approval or OAuth.'
POWERSHELL;

    return response($script."\r\n", 200, [
        'Content-Type' => 'text/plain; charset=UTF-8',
        'Content-Disposition' => 'attachment; filename="KMJ-CodeBridge-ChatGPT-Desktop.ps1"',
        'Cache-Control' => 'public, max-age=300',
        'X-Content-Type-Options' => 'nosniff',
    ]);
})->name('codebridge.chatgpt.desktop.install');

Route::get('/', function (PublicProductCatalog $products) {
    $portfolio = $products->all();

    return Inertia::render('welcome', [
        'products' => $portfolio,
        'portfolioCount' => count($portfolio),
    ]);
})->name('home');

Route::get('products', function (PublicProductCatalog $products) {
    return Inertia::render('products/index', [
        'products' => $products->all(),
    ]);
})->name('products.index');

Route::get('products/{slug}', function (string $slug, PublicProductCatalog $products) {
    if (in_array($slug, KmjProductCatalog::LEGACY_CINEMA_VARIANT_SLUGS, true)) {
        return redirect()->route('products.show', [
            'slug' => KmjProductCatalog::CINEMA_PLATFORM_SLUG,
        ], 301);
    }

    $product = $products->find($slug);
    abort_if($product === null, 404);

    return Inertia::render('products/show', [
        'product' => $product,
    ]);
})->name('products.show');

Route::get('products/kmj-codebridge/terms', fn () => Inertia::render('products/codebridge/terms'))->name('products.codebridge.terms');
Route::get('products/kmj-codebridge/privacy', fn () => Inertia::render('products/codebridge/privacy'))->name('products.codebridge.privacy');
Route::get('products/kmj-codebridge/support', fn () => Inertia::render('products/codebridge/support'))->name('products.codebridge.support');

Route::get('company', fn () => Inertia::render('company'))->name('company');

Route::get('capabilities', fn () => Inertia::render('capabilities'))->name('capabilities');

Route::get('llms.txt', function (PublicProductCatalog $products) {
    $items = collect($products->all())
        ->map(function (array $product): string {
            $variants = isset($product['variants']) && is_array($product['variants'])
                ? ' | Configurations: '.implode(', ', $product['variants'])
                : '';

            return sprintf(
                '- %s | %s | %s%s | https://kmjtechno.com/products/%s',
                $product['name'],
                $product['category'],
                $product['lifecycle_label'],
                $variants,
                $product['slug'],
            );
        })
        ->implode("\n");

    $body = implode("\n", [
        '# KMJ TECHNO',
        '',
        '> INNOVATE | BUILD | SCALE',
        '',
        'KMJ TECHNO builds software, cloud infrastructure, AI engineering systems, immersive calibration, secure connectivity and cinema/experience products.',
        '',
        '## Product authority',
        'Public product claims are lifecycle-bound. Roadmap, development and preview labels must not be interpreted as production availability.',
        '',
        '## Products',
        $items,
        '',
        '## Important URLs',
        '- https://kmjtechno.com/products',
        '- https://kmjtechno.com/company',
        '- https://kmjtechno.com/capabilities',
        '- https://kmjtechno.com/trust',
        '- https://kmjtechno.com/legal',
        '- https://kmjtechno.com/products/kmj-codebridge/terms',
        '- https://kmjtechno.com/products/kmj-codebridge/privacy',
        '- https://kmjtechno.com/products/kmj-codebridge/support',
        '',
        'For current facts, prefer the canonical product page and lifecycle label over third-party summaries.',
    ]);

    return response($body."\n", 200, [
        'Content-Type' => 'text/plain; charset=UTF-8',
    ]);
})->name('llms');

Route::get('sitemap.xml', function (PublicProductCatalog $products) {
    abort_unless((bool) config('app.public_indexing', false), 404);

    $origin = rtrim((string) config('app.url'), '/');
    $paths = [
        '/',
        '/company',
        '/capabilities',
        '/products',
        '/trust',
        '/legal',
        '/terms',
        '/privacy',
        '/refund-policy',
        '/acceptable-use',
        '/cookie-policy',
        '/products/kmj-codebridge/terms',
        '/products/kmj-codebridge/privacy',
        '/products/kmj-codebridge/support',
        ...collect($products->all())
            ->pluck('slug')
            ->filter(fn (mixed $slug): bool => is_string($slug) && $slug !== '')
            ->map(fn (string $slug): string => '/products/'.$slug)
            ->all(),
    ];

    $urls = collect($paths)
        ->unique()
        ->map(fn (string $path): string => '<url><loc>'.htmlspecialchars(
            $origin.$path,
            ENT_XML1 | ENT_QUOTES,
            'UTF-8',
        ).'</loc></url>')
        ->implode('');

    $xml = '<?xml version="1.0" encoding="UTF-8"?>'
        .'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        .$urls
        .'</urlset>';

    return response($xml, 200, [
        'Content-Type' => 'application/xml; charset=UTF-8',
    ]);
})->name('sitemap');

Route::get('trust', fn () => Inertia::render('trust'))->name('trust');

Route::get('legal', fn () => Inertia::render('legal/index'))->name('legal.index');
Route::get('terms', fn () => Inertia::render('legal/terms'))->name('legal.terms');
Route::get('privacy', fn () => Inertia::render('legal/privacy'))->name('legal.privacy');
Route::get('refund-policy', fn () => Inertia::render('legal/refund-policy'))->name('legal.refund');
Route::get('acceptable-use', fn () => Inertia::render('legal/acceptable-use'))->name('legal.acceptable-use');
Route::get('cookie-policy', fn () => Inertia::render('legal/cookie-policy'))->name('legal.cookies');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('codebridge-oauth-link/{uid}', [CodeBridgeOAuthLinkController::class, 'show'])
        ->name('codebridge.oauth.show');
    Route::post('codebridge-oauth-link/{uid}', [CodeBridgeOAuthLinkController::class, 'approve'])
        ->name('codebridge.oauth.approve');

    Route::get('codebridge/pair', function (Request $request, CodeBridgeDevicePairingService $pairings) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $code = (string) $request->query('code', '');
        $pairing = $code !== '' ? $pairings->preview($code, $user->id, time()) : null;

        return view('codebridge-pair', ['pairing' => $pairing, 'code' => $code]);
    })->name('codebridge.pair');

    Route::post('codebridge/pair', function (Request $request, CodeBridgeDevicePairingService $pairings) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $v = $request->validate([
            'code' => ['required', 'string', 'max:32'],
            'tenant_id' => ['required', 'string', 'max:64'],
        ]);
        try {
            $pairings->approve($v['code'], $user->id, $v['tenant_id'], time());
        } catch (DomainException $e) {
            return back()->withErrors(['code' => $e->getMessage()]);
        }

        return redirect()->route('codebridge.pair', ['code' => $v['code']])
            ->with('status', 'CodeBridge device approved. You can return to the installer.');
    })->name('codebridge.pair.approve');

    Route::get('dashboard', function (
        Request $request,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
        CustomerReleaseAccess $releaseAccess,
        PublicProductCatalog $catalog,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $items = [];

        foreach ($organizations->forUser($user->id) as $organization) {
            $presentedEntitlements = [];

            foreach ($entitlements->forOrganization($organization['id']) as $entitlement) {
                $release = $releaseAccess->latestForOrganizationProduct(
                    $user->id,
                    $organization['id'],
                    $entitlement['product_id'],
                );
                $artifact = $release?->artifact;

                $entitlement['release'] = $release !== null && $artifact instanceof ReleaseArtifact
                    ? [
                        'id' => (string) $release->getKey(),
                        'version' => $release->version,
                        'digest' => $release->artifact_digest,
                        'filename' => $artifact->filename,
                        'size_bytes' => $artifact->size_bytes,
                        'download_url' => route(
                            'customer.releases.download',
                            ['release' => $release->getKey()],
                            false,
                        ),
                    ]
                    : null;

                $entitlement['service'] = null;
                if ($entitlement['product_slug'] === 'kmj-codebridge') {
                    $license = DB::table('kslp_licenses')
                        ->where('customer_id', $organization['id'])
                        ->where('product', 'KMJ_CODEBRIDGE')
                        ->where('status', 'active')
                        ->whereNull('revoked_at')
                        ->where('starts_at', '<=', now())
                        ->where('expires_at', '>', now())
                        ->oldest('created_at')
                        ->first();
                    $plan = $license
                        ? DB::table('plans')->where('code', 'codebridge.'.$license->plan)->where('status', 'active')->first()
                        : null;
                    $features = $plan && is_string($plan->features)
                        ? json_decode($plan->features, true)
                        : null;
                    $permissions = collect(is_array($features) ? $features : [])
                        ->filter(fn (mixed $enabled, string $permission): bool => $enabled === true
                            && in_array($permission, ['read', 'write', 'execute'], true))
                        ->keys()
                        ->values()
                        ->all();

                    $entitlement['service'] = [
                        'kind' => 'codebridge',
                        'plan' => $license?->plan,
                        'license_status' => $license !== null ? (string) $license->status : 'setup_required',
                        'license_expires_at' => $license?->expires_at,
                        'managed_devices' => DB::table('codebridge_device_credentials')
                            ->where('tenant_id', $organization['id'])
                            ->whereNull('revoked_at')
                            ->where('expires_at_epoch', '>', time())
                            ->count(),
                        'pending_pairings' => DB::table('codebridge_device_pairings')
                            ->where('tenant_id', $organization['id'])
                            ->where('status', 'pending')
                            ->where('expires_at', '>', now())
                            ->count(),
                        'endpoint' => (string) config('codebridge_oauth.resource'),
                        'oauth_ready' => app(OAuthServer::class)->enabled(),
                        'permissions' => $permissions,
                    ];
                }

                $presentedEntitlements[] = $entitlement;
            }

            $organization['entitlements'] = $presentedEntitlements;
            $items[] = $organization;
        }

        return Inertia::render('dashboard', [
            'organizations' => $items,
            'hasPasskey' => $user->passkeys()->exists(),
            'catalog' => collect($catalog->all())
                ->map(fn (array $product): array => [
                    'slug' => $product['slug'],
                    'name' => $product['name'],
                    'summary' => $product['summary'],
                    'category' => $product['category'],
                    'lifecycle_label' => $product['lifecycle_label'],
                    'purchase_enabled' => (bool) $product['purchase_enabled'],
                    'image_path' => $product['image_path'] ?? null,
                ])
                ->values()
                ->all(),
        ]);
    })->name('dashboard');

    Route::get('services/kmj-codebridge', function (
        Request $request,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
        OAuthServer $oauth,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $access = collect($organizations->forUser($user->id))
            ->map(function (array $organization) use ($entitlements): ?array {
                $entitlement = collect($entitlements->forOrganization($organization['id']))
                    ->first(fn (array $item): bool => $item['product_slug'] === 'kmj-codebridge'
                        && $item['status'] === 'active');

                return is_array($entitlement)
                    ? ['organization' => $organization, 'entitlement' => $entitlement]
                    : null;
            })
            ->filter()
            ->first();

        abort_unless(is_array($access), 404);
        $organization = $access['organization'];
        $entitlement = $access['entitlement'];

        $license = DB::table('kslp_licenses')
            ->where('customer_id', $organization['id'])
            ->where('product', 'KMJ_CODEBRIDGE')
            ->where('status', 'active')
            ->whereNull('revoked_at')
            ->where('starts_at', '<=', now())
            ->where('expires_at', '>', now())
            ->oldest('created_at')
            ->first();
        $plan = $license
            ? DB::table('plans')->where('code', 'codebridge.'.$license->plan)->where('status', 'active')->first()
            : null;
        $features = $plan && is_string($plan->features) ? json_decode($plan->features, true) : null;
        $limits = $plan && is_string($plan->limits) ? json_decode($plan->limits, true) : null;
        $permissions = collect(is_array($features) ? $features : [])
            ->filter(fn (mixed $enabled, string $permission): bool => $enabled === true
                && in_array($permission, ['read', 'write', 'execute'], true))
            ->keys()
            ->values()
            ->all();

        $connectedClients = DB::table('codebridge_oauth_refresh_tokens as tokens')
            ->join('codebridge_oauth_clients as clients', 'clients.client_id', '=', 'tokens.client_id')
            ->where('tokens.user_id', $user->id)
            ->whereNull('tokens.revoked_at_epoch')
            ->where('tokens.expires_at_epoch', '>', time())
            ->get([
                'tokens.client_id',
                'tokens.family_id',
                'tokens.scope',
                'tokens.created_at',
                'tokens.updated_at',
                'clients.client_name',
            ])
            ->groupBy('client_id')
            ->map(function ($rows): array {
                $first = $rows->first();
                $scopes = $rows
                    ->pluck('scope')
                    ->filter(fn (mixed $scope): bool => is_string($scope) && $scope !== '')
                    ->flatMap(fn (string $scope): array => preg_split('/\\s+/', trim($scope)) ?: [])
                    ->filter()
                    ->unique()
                    ->values()
                    ->all();

                return [
                    'client_id' => (string) $first->client_id,
                    'client_name' => (string) $first->client_name,
                    'sessions' => $rows->pluck('family_id')->unique()->count(),
                    'scopes' => $scopes,
                    'connected_at' => $rows->min('created_at'),
                    'last_active_at' => $rows->max('updated_at'),
                ];
            })
            ->values()
            ->all();

        return Inertia::render('services/codebridge', [
            'organization' => $organization,
            'entitlement' => $entitlement,
            'service' => [
                'endpoint' => $oauth->resource(),
                'oauth_ready' => $oauth->enabled(),
                'plan' => $license?->plan,
                'license_status' => $license !== null ? (string) $license->status : 'setup_required',
                'license_starts_at' => $license?->starts_at,
                'license_expires_at' => $license?->expires_at,
                'permissions' => $permissions,
                'device_limit' => is_array($limits) && is_int($limits['devices'] ?? null) ? $limits['devices'] : null,
                'managed_devices' => DB::table('codebridge_device_credentials')
                    ->where('tenant_id', $organization['id'])
                    ->whereNull('revoked_at')
                    ->where('expires_at_epoch', '>', time())
                    ->count(),
                'pending_pairings' => DB::table('codebridge_device_pairings')
                    ->where('status', 'pending')
                    ->where('expires_at', '>', now())
                    ->count(),
                'connected_clients' => $connectedClients,
                'access_token_ttl_seconds' => (int) config('codebridge_oauth.access_token_ttl', 900),
            ],
        ]);
    })->name('services.codebridge');

    Route::post('services/kmj-codebridge/oauth-clients/{clientId}/revoke', function (
        Request $request,
        string $clientId,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        abort_unless((bool) preg_match('/\\A[A-Za-z0-9._-]{1,64}\\z/D', $clientId), 404);

        $now = time();
        $revoked = DB::table('codebridge_oauth_refresh_tokens')
            ->where('user_id', $user->id)
            ->where('client_id', $clientId)
            ->whereNull('revoked_at_epoch')
            ->update([
                'revoked_at_epoch' => $now,
                'updated_at' => now(),
            ]);

        DB::table('codebridge_oauth_codes')
            ->where('user_id', $user->id)
            ->where('client_id', $clientId)
            ->whereNull('consumed_at_epoch')
            ->update([
                'consumed_at_epoch' => $now,
                'updated_at' => now(),
            ]);

        return back()->with(
            'status',
            $revoked > 0
                ? 'CodeBridge client access revoked. Existing access tokens expire shortly.'
                : 'No active CodeBridge client access was found.',
        );
    })->name('services.codebridge.oauth.revoke');

    Route::get('customer/releases/{release}/download', function (
        Request $request,
        string $release,
        CustomerReleaseAccess $releaseAccess,
        ReleaseArtifactDelivery $delivery,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $downloadable = $releaseAccess->downloadableForUser($user->id, $release);
        abort_unless($downloadable !== null, 404);

        try {
            return $delivery->download($downloadable);
        } catch (Throwable $exception) {
            report($exception);
            abort(503, 'The verified release artifact is temporarily unavailable.');
        }
    })->name('customer.releases.download');

    Route::get('operator', function (
        Request $request,
        PlatformOwnerAccess $access,
        OrganizationCapabilityContext $capabilities,
        PublicProductCatalog $publicProducts,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $recentOrders = CommercialOrder::query()
            ->latest('created_at')
            ->limit(20)
            ->get(['id', 'organization_id', 'product_id', 'status', 'currency', 'amount_minor', 'created_at'])
            ->map(function (CommercialOrder $order) use ($capabilities, $user): array {
                $organizationId = (string) $order->getAttribute('organization_id');
                $productId = (string) $order->getAttribute('product_id');
                $activeEntitlement = Entitlement::query()
                    ->where('organization_id', $organizationId)
                    ->where('product_id', $productId)
                    ->where('status', 'active')
                    ->oldest('created_at')
                    ->oldest('id')
                    ->first();
                $hasActivePolicy = EntitlementPolicy::query()
                    ->where('product_id', $productId)
                    ->where('status', 'active')
                    ->exists();
                $fulfillmentState = match (true) {
                    $order->getAttribute('status') !== 'confirmed' => 'awaiting_confirmation',
                    $activeEntitlement instanceof Entitlement => 'entitled',
                    $hasActivePolicy => 'ready',
                    default => 'blocked_no_policy',
                };

                return [
                    'id' => $order->getKey(),
                    'organization_id' => $organizationId,
                    'product_id' => $productId,
                    'status' => $order->getAttribute('status'),
                    'currency' => $order->getAttribute('currency'),
                    'amount_minor' => $order->getAttribute('amount_minor'),
                    'created_at' => $order->getAttribute('created_at')?->toISOString(),
                    'fulfillment_state' => $fulfillmentState,
                    'entitlement_id' => $activeEntitlement?->getKey(),
                    'can_manage_license' => $activeEntitlement instanceof Entitlement
                        && $capabilities->allows($user->id, $organizationId, 'license.manage'),
                ];
            })->all();

        $managedProducts = Product::query()
            ->orderBy('sort_order')
            ->orderBy('name')
            ->get([
                'id',
                'slug',
                'name',
                'status',
                'lifecycle',
                'is_public',
                'sort_order',
                'image_path',
                'summary',
                'purchase_enabled',
                'licensing_enabled',
            ]);

        $catalogProducts = $managedProducts
            ->map(function (Product $product): array {
                $productId = (string) $product->getKey();

                return [
                    'id' => $productId,
                    'slug' => (string) $product->getAttribute('slug'),
                    'name' => (string) $product->getAttribute('name'),
                    'status' => (string) $product->getAttribute('status'),
                    'active_policy_count' => EntitlementPolicy::query()
                        ->where('product_id', $productId)
                        ->where('status', 'active')
                        ->count(),
                    'active_entitlement_count' => Entitlement::query()
                        ->where('product_id', $productId)
                        ->where('status', 'active')
                        ->count(),
                ];
            })
            ->all();

        return Inertia::render('operator', [
            'metrics' => [
                'users' => User::query()->count(),
                'organizations' => Organization::query()->count(),
                'entitlements' => Entitlement::query()->count(),
                'orders' => CommercialOrder::query()->count(),
                'confirmed_orders' => CommercialOrder::query()->where('status', 'confirmed')->count(),
            ],
            'catalogProducts' => $catalogProducts,
            'recentOrders' => $recentOrders,
            'products' => $managedProducts,
        ]);
    })->name('operator.index')->middleware('password.confirm');

    Route::post('operator/orders/{order}/fulfill', function (
        Request $request,
        string $order,
        PlatformOwnerAccess $access,
        EntitlementIssuer $issuer,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $commercialOrder = CommercialOrder::query()
            ->whereKey($order)
            ->where('status', 'confirmed')
            ->firstOrFail();
        $organizationId = (string) $commercialOrder->getAttribute('organization_id');
        $productId = (string) $commercialOrder->getAttribute('product_id');
        $idempotencyKey = 'commercial-order:'.$commercialOrder->getKey();

        $existing = Entitlement::query()
            ->where('idempotency_key', $idempotencyKey)
            ->first();

        if ($existing instanceof Entitlement) {
            abort_unless(
                $existing->getAttribute('organization_id') === $organizationId
                && $existing->getAttribute('product_id') === $productId,
                409,
            );

            return redirect()->route('operator.index');
        }

        abort_if(
            Entitlement::query()
                ->where('organization_id', $organizationId)
                ->where('product_id', $productId)
                ->where('status', 'active')
                ->exists(),
            409,
            'An active entitlement already exists for this organization and product.',
        );

        $policy = EntitlementPolicy::query()
            ->where('product_id', $productId)
            ->where('status', 'active')
            ->oldest('created_at')
            ->oldest('id')
            ->firstOrFail();

        $issuer->issue($organizationId, $policy, $idempotencyKey);

        return redirect()->route('operator.index');
    })->name('operator.orders.fulfill')->middleware('password.confirm');

    Route::post('operator/orders/{order}/sandbox-license', function (
        Request $request,
        string $order,
        PlatformOwnerAccess $access,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        $commercialOrder = CommercialOrder::query()
            ->whereKey($order)
            ->where('status', 'confirmed')
            ->firstOrFail();
        $organizationId = (string) $commercialOrder->getAttribute('organization_id');
        $productId = (string) $commercialOrder->getAttribute('product_id');

        abort_unless($capabilities->allows($user->id, $organizationId, 'license.manage'), 403);

        $entitlement = Entitlement::query()
            ->where('organization_id', $organizationId)
            ->where('product_id', $productId)
            ->where('status', 'active')
            ->oldest('created_at')
            ->oldest('id')
            ->firstOrFail();

        $license = $licenses->issue(
            $organizationId,
            $productId,
            $entitlement->getKey(),
            new ImmutableDateTime('+30 minutes'),
        );
        $validation = $licenses->validate($license);
        $claims = $validation['claims'];
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        $audit->record(
            'sandbox_license.issued',
            $user->id,
            $organizationId,
            is_string($jti) ? $jti : null,
            'success',
            [
                'entitlement_id' => $entitlement->getKey(),
                'commercial_order_id' => $commercialOrder->getKey(),
                'source' => 'operator_handoff',
            ],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license', [
                'token' => $license,
                'validation' => $validation,
            ]);
    })->name('operator.orders.sandbox-license')->middleware('password.confirm');

    Route::get('sandbox-licenses', function (
        Request $request,
        OrganizationDirectory $organizations,
        OrganizationCapabilityContext $capabilities,
        EntitlementReader $entitlements,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $items = collect($organizations->forUser($user->id))
            ->map(function (array $organization) use ($entitlements): array {
                $organization['entitlements'] = $entitlements->forOrganization($organization['id']);

                return $organization;
            })
            ->values()
            ->all();
        $organizationIds = collect($items)
            ->pluck('id')
            ->filter(fn (mixed $id): bool => is_string($id) && $capabilities->allows($user->id, $id, 'license.manage'))
            ->values()
            ->all();
        $auditEvents = $organizationIds === []
            ? []
            : LicenseAuditEvent::query()
                ->whereIn('organization_id', $organizationIds)
                ->latest('id')
                ->limit(20)
                ->get(['id', 'organization_id', 'action', 'status', 'jti', 'metadata', 'created_at'])
                ->map(fn (LicenseAuditEvent $event): array => [
                    'id' => $event->getKey(),
                    'organization_id' => $event->getAttribute('organization_id'),
                    'action' => $event->getAttribute('action'),
                    'status' => $event->getAttribute('status'),
                    'jti' => $event->getAttribute('jti'),
                    'metadata' => $event->getAttribute('metadata'),
                    'created_at' => $event->getAttribute('created_at')?->toISOString(),
                ])
                ->all();

        return Inertia::render('sandbox-licenses', [
            'organizations' => $items,
            'licenseResult' => $request->session()->get('sandbox_license'),
            'validationResult' => $request->session()->get('sandbox_license_validation'),
            'auditEvents' => $auditEvents,
            'validationEngine' => (string) config('services.kmj_sandbox_licensing.validation_engine', 'php'),
        ]);
    })->name('sandbox-licenses.index');

    Route::post('organizations', function (Request $request, AuthorityBootstrapper $bootstrapper) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:160'],
        ]);

        $bootstrapper->createOrganizationWithSandboxAccess(
            $validated['name'],
            $user->id,
        );

        return redirect()->route('dashboard');
    })->name('organizations.store');

    Route::post('sandbox-licenses', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'entitlement_id' => ['required', 'uuid'],
        ]);

        abort_unless($capabilities->allows($user->id, $validated['organization_id'], 'license.manage'), 403);

        $entitlement = Entitlement::query()
            ->whereKey($validated['entitlement_id'])
            ->where('organization_id', $validated['organization_id'])
            ->where('status', 'active')
            ->firstOrFail();

        $license = $licenses->issue(
            (string) $entitlement->getAttribute('organization_id'),
            (string) $entitlement->getAttribute('product_id'),
            $entitlement->getKey(),
            new ImmutableDateTime('+30 minutes'),
        );
        $validation = $licenses->validate($license);
        $claims = $validation['claims'];
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        $audit->record(
            'sandbox_license.issued',
            $user->id,
            $validated['organization_id'],
            is_string($jti) ? $jti : null,
            'success',
            ['entitlement_id' => $validated['entitlement_id']],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license', [
                'token' => $license,
                'validation' => $validation,
            ]);
    })->name('sandbox-licenses.store');

    Route::post('sandbox-licenses/validate', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'license' => ['required', 'string', 'max:8192'],
        ]);

        abort_unless($capabilities->allows($user->id, $validated['organization_id'], 'license.manage'), 403);

        $result = $licenses->validate($validated['license']);
        $claims = $result['claims'];
        $organizationId = is_array($claims) ? ($claims['organization_id'] ?? null) : null;
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        if (is_string($organizationId)) {
            abort_unless(hash_equals($validated['organization_id'], $organizationId), 422);
        }

        $audit->record(
            'sandbox_license.validated',
            $user->id,
            is_string($organizationId) ? $organizationId : null,
            is_string($jti) ? $jti : null,
            $result['valid'] ? 'valid' : 'invalid',
            ['reason' => $result['reason']],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license_validation', $result);
    })->name('sandbox-licenses.validate');

    Route::post('sandbox-licenses/revoke', function (
        Request $request,
        OrganizationCapabilityContext $capabilities,
        SandboxLicenseLifecycle $licenses,
        LicenseAuditRecorder $audit,
    ) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $validated = $request->validate([
            'organization_id' => ['required', 'uuid'],
            'license' => ['required', 'string', 'max:8192'],
            'reason' => ['nullable', 'string', 'max:255'],
        ]);

        abort_unless($capabilities->allows($user->id, $validated['organization_id'], 'license.manage'), 403);

        $result = $licenses->validate($validated['license']);
        $claims = $result['claims'];
        $organizationId = is_array($claims) ? ($claims['organization_id'] ?? null) : null;
        $jti = is_array($claims) ? ($claims['jti'] ?? null) : null;

        abort_unless(is_string($organizationId) && is_string($jti), 422);
        abort_unless(hash_equals($validated['organization_id'], $organizationId), 422);

        $licenses->revoke($jti, $validated['reason'] ?? null);
        $audit->record(
            'sandbox_license.revoked',
            $user->id,
            $organizationId,
            $jti,
            'revoked',
            ['reason' => $validated['reason'] ?? null],
        );

        return redirect()
            ->route('sandbox-licenses.index')
            ->with('sandbox_license_validation', $licenses->validate($validated['license']));
    })->name('sandbox-licenses.revoke')->middleware('password.confirm');
    require __DIR__.'/kslp-admin.php';
    require __DIR__.'/codebridge-admin.php';
});

require __DIR__.'/settings.php';
