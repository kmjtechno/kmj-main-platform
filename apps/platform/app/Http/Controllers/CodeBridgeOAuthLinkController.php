<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Commerce\KmjProductCatalog;
use App\Services\Commerce\PublicProductCatalog;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;
use KMJ\MainPlatform\Entitlements\Services\EntitlementReader;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;
use RuntimeException;

class CodeBridgeOAuthLinkController extends Controller
{
    public function show(
        Request $request,
        string $uid,
        PublicProductCatalog $products,
        OrganizationDirectory $organizations,
        EntitlementReader $entitlements,
    ): View {

        $this->assertUid($uid);
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $service = $products->find(KmjProductCatalog::CODEBRIDGE_SLUG);
        $registrations = [];

        foreach ($organizations->forUser($user->id) as $organization) {
            $codeBridgeEntitlements = collect($entitlements->forOrganization($organization['id']))
                ->filter(fn (array $entitlement): bool => $entitlement['product_slug'] === KmjProductCatalog::CODEBRIDGE_SLUG)
                ->values()
                ->all();

            if ($codeBridgeEntitlements === []) {
                continue;
            }

            $registrations[] = [
                'organization' => $organization,
                'entitlements' => $codeBridgeEntitlements,
            ];
        }

        return view('codebridge-oauth-link', [
            'uid' => $uid,
            'user' => $user,
            'service' => $service,
            'registrations' => $registrations,
            'scopes' => [
                'codebridge:read' => 'Inspect authorized devices, projects, Git status, and approved files.',
                'codebridge:write' => 'Apply hash-guarded changes only inside authorized project paths.',
                'codebridge:execute' => 'Run administrator-configured quality gates; arbitrary shell access is not granted.',
            ],
        ]);
    }

    public function approve(Request $request, string $uid): RedirectResponse
    {
        $this->assertUid($uid);
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        $secret = trim((string) config('services.codebridge_oauth.link_secret'));
        if (strlen($secret) < 32) {
            $secretFile = (string) config(
                'services.codebridge_oauth.link_secret_file',
                '/etc/kmj-codebridge-oauth/bridge-secret',
            );
            $secret = is_readable($secretFile)
                ? trim((string) file_get_contents($secretFile))
                : '';
        }
        if (strlen($secret) < 32) {
            throw new RuntimeException('CodeBridge OAuth link secret is not configured.');
        }

        $payload = $this->base64UrlEncode(json_encode([
            'uid' => $uid,
            'sub' => (string) $user->getKey(),
            'email' => (string) $user->email,
            'name' => (string) $user->name,
            'exp' => time() + 60,
        ], JSON_THROW_ON_ERROR));

        $signature = hash_hmac('sha256', $payload, $secret);

        return redirect()->to(
            '/codebridge-oauth/interaction/'.$uid.'/resume'
            .'?assertion='.rawurlencode($payload)
            .'&sig='.rawurlencode($signature),
        );
    }

    private function assertUid(string $uid): void
    {
        abort_unless((bool) preg_match('/^[A-Za-z0-9_-]{16,160}$/', $uid), 404);
    }

    private function base64UrlEncode(string $value): string
    {
        return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    }
}
