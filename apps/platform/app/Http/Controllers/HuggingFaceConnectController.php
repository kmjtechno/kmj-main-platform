<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiProvider;
use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\AiProviders\HuggingFaceConnect;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use InvalidArgumentException;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/**
 * One-click Hugging Face connection for ModelFabric. The connected account must be a Free account with
 * no payment method (the owner attests this before sign-in), because a PRO or pay-as-you-go account
 * could be billed beyond free credits. A connected provider still needs per-model price evidence.
 */
final class HuggingFaceConnectController extends Controller
{
    public function __construct(
        private readonly ResolvesAiProviderScope $scope,
        private readonly ProviderManager $manager,
        private readonly HuggingFaceConnect $hf,
    ) {}

    public function metadata(): JsonResponse
    {
        return response()->json(
            $this->hf->metadata($this->clientId(), $this->redirectUri()),
            200,
            ['Cache-Control' => 'public, max-age=300'],
        );
    }

    public function start(Request $request): SymfonyResponse
    {
        $scope = $this->managing($request);
        $request->validate(['free_account_confirmed' => ['accepted']]);
        try {
            $flow = $this->hf->begin($this->clientId(), $this->redirectUri());
        } catch (InvalidArgumentException $exception) {
            return back()->withErrors(['provider' => 'Cannot start sign-in: '.$exception->getMessage()]);
        }
        $request->session()->put('ai_provider_hf_oauth', [
            'verifier' => $flow['verifier'],
            'state' => $flow['state'],
            'user' => (int) $this->user($request)->id,
            'organization' => $scope['organization_id'],
            'expires' => time() + 600,
        ]);

        return Inertia::location($flow['url']);
    }

    public function callback(Request $request): RedirectResponse
    {
        $scope = $this->managing($request);
        // Single use: a replayed or forged callback finds nothing to redeem.
        $pending = $request->session()->pull('ai_provider_hf_oauth');
        $index = redirect()->route('ai-providers.index');
        if (! is_array($pending) || ($pending['expires'] ?? 0) < time()
            || ($pending['user'] ?? null) !== (int) $this->user($request)->id
            || ($pending['organization'] ?? null) !== $scope['organization_id']) {
            return $index->withErrors(['provider' => 'Sign-in expired or was not started here. Start again.']);
        }
        if ($request->query('error') !== null) {
            return $index->withErrors(['provider' => 'Authorization was declined or canceled. No provider was added.']);
        }
        $returnedState = $request->query('state');
        $expectedState = $pending['state'] ?? null;
        if (! is_string($returnedState) || ! is_string($expectedState) || ! hash_equals($expectedState, $returnedState)) {
            return $index->withErrors(['provider' => 'Sign-in session mismatch. Start again.']);
        }
        $code = $request->query('code');
        $verifier = $pending['verifier'] ?? null;
        if (! is_string($code) || ! is_string($verifier)) {
            return $index->withErrors(['provider' => 'Invalid sign-in response. Start again.']);
        }

        try {
            $token = $this->hf->exchange($code, $verifier, $this->clientId(), $this->redirectUri());
            $existing = AiProvider::query()->where('organization_id', $scope['organization_id'])->where('preset', 'huggingface')->first();
            // Reconnecting replaces the key of the existing provider instead of creating a duplicate.
            $provider = $existing instanceof AiProvider
                ? $this->manager->update($existing, ['api_key' => $token])
                : $this->manager->create($scope['organization_id'], (int) $this->user($request)->id, [
                    'preset' => 'huggingface',
                    'name' => 'Hugging Face',
                    'api_key' => $token,
                ]);
        } catch (InvalidArgumentException $exception) {
            return $index->withErrors(['provider' => 'Hugging Face sign-in failed: '.$exception->getMessage()]);
        }
        $tested = $this->manager->test($provider);

        OperatorActionAudit::query()->create([
            'actor_user_id' => (int) $this->user($request)->id,
            'action' => 'model_fabric.huggingface_connected',
            'outcome' => 'saved',
            'metadata' => ['scope' => HuggingFaceConnect::SCOPE, 'free_account_attested' => true, 'paid_inference_enabled' => false],
        ]);

        return $index->with('status', $tested->health === 'ok'
            ? 'Hugging Face connected. '.count($tested->models_cache ?? []).' models found; approve free ones on ModelFabric. No inference enabled yet.'
            : 'Hugging Face authorized and the key is stored securely. Verification is pending: '.$tested->health.'. No inference enabled.');
    }

    private function clientId(): string
    {
        return (string) preg_replace('#\Ahttp://#', 'https://', route('ai-providers.huggingface.metadata'));
    }

    private function redirectUri(): string
    {
        return (string) preg_replace('#\Ahttp://#', 'https://', route('ai-providers.huggingface.callback'));
    }

    private function user(Request $request): User
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        return $user;
    }

    /** @return array{organization_id: string, can_manage: bool} */
    private function managing(Request $request): array
    {
        $scope = $this->scope->for($this->user($request));
        abort_unless($scope['can_manage'], 403);

        return $scope;
    }
}
