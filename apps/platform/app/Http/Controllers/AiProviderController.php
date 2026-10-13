<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\OpenRouterConnect;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Inertia\Inertia;
use Inertia\Response;
use InvalidArgumentException;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

final class AiProviderController extends Controller
{
    public function __construct(
        private readonly ResolvesAiProviderScope $scope,
        private readonly ProviderManager $manager,
        private readonly OpenRouterConnect $openRouter,
    ) {}

    public function index(Request $request): Response
    {
        $scope = $this->scope->for($this->user($request));

        return Inertia::render('services/ai-providers', [
            'status' => session('status'),
            'canManage' => $scope['can_manage'],
            'presets' => collect($this->manager->presets())
                ->map(fn (array $preset, string $key): array => [
                    'key' => $key,
                    'label' => $preset['label'],
                    'free_tier' => $preset['free_tier'],
                    'custom' => $preset['base_url'] === null,
                ])->values(),
            'providers' => AiProvider::query()
                ->where('organization_id', $scope['organization_id'])
                ->orderBy('name')->get()
                ->map(fn (AiProvider $provider): array => $this->manager->present($provider))->values(),
        ]);
    }

    public function store(Request $request): RedirectResponse
    {
        $scope = $this->managing($request);
        $data = $request->validate([
            // Optional: when empty the provider's own label is used (made unique automatically).
            'name' => ['nullable', 'string', 'min:2', 'max:80', 'regex:/\A[\pL\pN ._@+()\/&\'-]+\z/u',
                Rule::unique('ai_providers', 'name')->where('organization_id', $scope['organization_id'])],
            'preset' => ['required', Rule::in(array_keys($this->manager->presets()))],
            'base_url' => ['nullable', 'string', 'max:255'],
            'api_key' => ['required', 'string', 'min:8', 'max:512', 'regex:/\A\S+\z/'],
            // Zero-spend is global: billed inference cannot be enabled from this page.
            'free_only' => ['prohibited'],
        ]);

        try {
            $label = (string) ($this->manager->presets()[$data['preset']]['label'] ?? 'Provider');
            $data['name'] = filled($data['name'] ?? null) ? $data['name'] : $this->freeName($scope['organization_id'], $label);
            $this->manager->create($scope['organization_id'], (int) $this->user($request)->id, $data);
        } catch (InvalidArgumentException $exception) {
            return back()->withErrors(['base_url' => 'Endpoint rejected: '.$exception->getMessage()]);
        } catch (UniqueConstraintViolationException) {
            // A duplicate submission that raced past the validator.
            return back()->withErrors(['name' => 'A provider with this name already exists.']);
        }

        return back()->with('status', 'Provider added. Run Test connection to verify it.');
    }

    public function update(Request $request, string $provider): RedirectResponse
    {
        $model = $this->find($request, $provider, true);
        $data = $request->validate([
            'name' => ['sometimes', 'string', 'min:2', 'max:80', 'regex:/\A[\pL\pN ._@+()\/&\'-]+\z/u',
                Rule::unique('ai_providers', 'name')->where('organization_id', $model->organization_id)->ignore($model->id)],
            'api_key' => ['sometimes', 'nullable', 'string', 'min:8', 'max:512', 'regex:/\A\S+\z/'],
            'enabled' => ['sometimes', 'boolean'],
            'free_only' => ['prohibited'],
            'default_model' => ['sometimes', 'nullable', 'string', 'max:128'],
            'fallback_models' => ['sometimes', 'array', 'max:5'],
            'fallback_models.*' => ['string', 'max:128'],
        ]);

        try {
            $this->manager->update($model, $data);
        } catch (InvalidArgumentException $exception) {
            return back()->withErrors(['provider' => 'Not saved: '.$exception->getMessage()]);
        }

        return back()->with('status', 'Provider updated.');
    }

    /** Start the OpenRouter sign-in (Google/GitHub there); the key comes back to the callback. */
    public function connectOpenRouter(Request $request): SymfonyResponse
    {
        $scope = $this->managing($request);
        try {
            // Never derive an OAuth callback from a caller-supplied Host header.
            // Require CloudOS/APP_URL to declare its canonical public HTTPS origin.
            $origin = (string) config('app.url', '');
            $url = parse_url($origin);
            if (! is_array($url)
                || ($url['scheme'] ?? null) !== 'https'
                || empty($url['host'])
                || isset($url['user']) || isset($url['pass'])
                || isset($url['query']) || isset($url['fragment'])
                || (isset($url['path']) && ! in_array($url['path'], ['', '/'], true))) {
                throw new InvalidArgumentException('canonical_https_app_url_required');
            }
            $callback = rtrim($origin, '/').route('ai-providers.openrouter.callback', [], false);
            $flow = $this->openRouter->begin($callback);
        } catch (InvalidArgumentException $exception) {
            return back()->withErrors(['provider' => 'Cannot start sign-in: '.$exception->getMessage()]);
        }
        $request->session()->put('ai_provider_oauth', [
            'verifier' => $flow['verifier'],
            'user' => (int) $this->user($request)->id,
            'organization' => $scope['organization_id'],
            'expires' => time() + 600,
        ]);

        return Inertia::location($flow['url']);
    }

    public function openRouterCallback(Request $request): RedirectResponse
    {
        $scope = $this->managing($request);
        // Single use: a replayed or forged callback finds nothing to redeem.
        $pending = $request->session()->pull('ai_provider_oauth');
        $index = redirect()->route('ai-providers.index');
        if (! is_array($pending) || ($pending['expires'] ?? 0) < time()
            || ($pending['user'] ?? null) !== (int) $this->user($request)->id
            || ($pending['organization'] ?? null) !== $scope['organization_id']) {
            return $index->withErrors(['provider' => 'Sign-in expired or was not started here. Start again.']);
        }

        try {
            $key = $this->openRouter->exchange((string) $request->query('code', ''), (string) $pending['verifier']);
            $provider = $this->manager->create($scope['organization_id'], (int) $this->user($request)->id, [
                'preset' => 'openrouter',
                'name' => $this->freeName($scope['organization_id'], 'OpenRouter'),
                'api_key' => $key,
            ]);
        } catch (InvalidArgumentException $exception) {
            return $index->withErrors(['provider' => 'OpenRouter sign-in failed: '.$exception->getMessage()]);
        }
        $tested = $this->manager->test($provider);

        if ($tested->health !== 'ok') {
            return $index->with('status', 'OpenRouter authorization saved, but connection verification failed ('.$tested->health.'). Inference remains blocked until a successful connection test.');
        }

        return $index->with('status', 'OpenRouter connected and verified ('.count($tested->models_cache ?? []).' models discovered). Only ":free" models are admitted.');
    }

    private function freeName(string $organizationId, string $base): string
    {
        for ($i = 1; $i <= 20; $i++) {
            $name = $i === 1 ? $base : $base.' '.$i;
            if (! AiProvider::query()->where('organization_id', $organizationId)->where('name', $name)->exists()) {
                return $name;
            }
        }

        return $base.' '.bin2hex(random_bytes(3));
    }

    public function test(Request $request, string $provider): RedirectResponse
    {
        $tested = $this->manager->test($this->find($request, $provider, true));

        return back()->with('status', $tested->health === 'ok'
            ? 'Connection verified; '.count($tested->models_cache ?? []).' models discovered.'
            : 'Connection check finished: '.$tested->health.'.');
    }

    public function destroy(Request $request, string $provider): RedirectResponse
    {
        $request->validate(['confirm' => ['required', 'in:DELETE']]);
        $this->manager->delete($this->find($request, $provider, true));

        return back()->with('status', 'Provider and its stored key were deleted.');
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

    private function find(Request $request, string $id, bool $manage): AiProvider
    {
        $scope = $manage ? $this->managing($request) : $this->scope->for($this->user($request));
        abort_unless(preg_match('/\A[0-9a-f-]{36}\z/', $id) === 1, 404);

        // The organization filter is the tenant boundary: another tenant's id is a 404.
        return AiProvider::query()
            ->where('organization_id', $scope['organization_id'])
            ->whereKey($id)->firstOrFail();
    }
}
