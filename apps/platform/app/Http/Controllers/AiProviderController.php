<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Inertia\Inertia;
use Inertia\Response;
use InvalidArgumentException;

final class AiProviderController extends Controller
{
    public function __construct(
        private readonly ResolvesAiProviderScope $scope,
        private readonly ProviderManager $manager,
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
            'name' => ['required', 'string', 'min:2', 'max:80', 'regex:/\A[\pL\pN ._-]+\z/u',
                Rule::unique('ai_providers', 'name')->where('organization_id', $scope['organization_id'])],
            'preset' => ['required', Rule::in(array_keys($this->manager->presets()))],
            'base_url' => ['nullable', 'string', 'max:255'],
            'api_key' => ['required', 'string', 'min:8', 'max:512', 'regex:/\A\S+\z/'],
            'free_only' => ['sometimes', 'boolean'],
        ]);

        try {
            $this->manager->create($scope['organization_id'], (int) $this->user($request)->id, $data);
        } catch (InvalidArgumentException $exception) {
            return back()->withErrors(['base_url' => 'Endpoint rejected: '.$exception->getMessage()]);
        }

        return back()->with('status', 'Provider added. Run Test connection to verify it.');
    }

    public function update(Request $request, string $provider): RedirectResponse
    {
        $model = $this->find($request, $provider, true);
        $data = $request->validate([
            'name' => ['sometimes', 'string', 'min:2', 'max:80', 'regex:/\A[\pL\pN ._-]+\z/u',
                Rule::unique('ai_providers', 'name')->where('organization_id', $model->organization_id)->ignore($model->id)],
            'api_key' => ['sometimes', 'nullable', 'string', 'min:8', 'max:512', 'regex:/\A\S+\z/'],
            'enabled' => ['sometimes', 'boolean'],
            'free_only' => ['sometimes', 'boolean'],
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
