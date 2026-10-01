<?php

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class CodeBridgeOAuthLinkController extends Controller
{
    public function show(Request $request, string $uid): View
    {
        $this->assertUid($uid);
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        return view('codebridge-oauth-link', [
            'uid' => $uid,
            'user' => $user,
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

        $secret = $this->linkSecret();

        $payload = $this->base64UrlEncode(json_encode([
            'v' => 1,
            'uid' => $uid,
            'sub' => (string) $user->getKey(),
            'email' => (string) $user->email,
            'name' => (string) $user->name,
            'iat' => time(),
            'exp' => time() + 60,
            'nonce' => bin2hex(random_bytes(16)),
        ], JSON_THROW_ON_ERROR));

        $signature = $this->base64UrlEncode(hash_hmac('sha256', $payload, $secret, true));

        return redirect()->to('/codebridge-oauth-link/'.$uid.'/complete?assertion='.$payload.'.'.$signature);
    }

    private function linkSecret(): string
    {
        $configured = (string) config('services.codebridge_oauth.link_secret');
        if (strlen($configured) >= 32) {
            return $configured;
        }

        $appKey = (string) config('app.key');
        $rawAppKey = str_starts_with($appKey, 'base64:')
            ? base64_decode(substr($appKey, 7), true)
            : $appKey;

        abort_unless(is_string($rawAppKey) && strlen($rawAppKey) >= 32, 503, 'CodeBridge authorization is temporarily unavailable.');

        return hash_hmac('sha256', 'kmj-codebridge-oauth-link-v1', $rawAppKey);
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
