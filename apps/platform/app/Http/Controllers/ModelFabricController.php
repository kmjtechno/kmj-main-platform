<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiModelEvidence;
use App\Models\AiModelRequest;
use App\Models\AiProvider;
use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\AiProviders\ModelFabricGateway;
use App\Services\AiProviders\ModelFabricRouter;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Inertia\Inertia;
use Inertia\Response;

/**
 * Owner console for the verified-zero cloud AI router (ADR-004). It records current price evidence
 * and shows exactly which routes qualify. It has no switch that allows paid or unknown-cost inference.
 */
final class ModelFabricController extends Controller
{
    private const MAX_EVIDENCE_DAYS = 30;

    public function __construct(
        private readonly PlatformOwnerAccess $access,
        private readonly ResolvesAiProviderScope $scope,
        private readonly ProviderManager $manager,
        private readonly ModelFabricRouter $router,
    ) {}

    public function index(Request $request): Response
    {
        $scope = $this->owner($request, false);
        $orgId = $scope['organization_id'];

        $providers = AiProvider::query()->where('organization_id', $orgId)->orderBy('name')->get();
        $evidence = AiModelEvidence::query()->where('organization_id', $orgId)->orderBy('model_id')->get();

        return Inertia::render('operator-modelfabric', [
            'status' => session('status'),
            'canManage' => $scope['can_manage'],
            'maxEvidenceDays' => self::MAX_EVIDENCE_DAYS,
            'providers' => $providers->map(function (AiProvider $provider): array {
                $presented = $this->manager->present($provider);
                $presented['discovered_models'] = array_slice($provider->models_cache ?? [], 0, 200);

                return $presented;
            })->values(),
            'evidence' => $evidence->map(fn (AiModelEvidence $row): array => [
                'id' => $row->id,
                'provider_id' => $row->ai_provider_id,
                'model_id' => $row->model_id,
                'price_evidence_url' => $row->price_evidence_url,
                'price_evidence_note' => $row->price_evidence_note,
                'verified_at' => $row->verified_at->toIso8601String(),
                'expires_at' => $row->expires_at->toIso8601String(),
                'data_handling' => $row->data_handling,
                'capabilities' => $row->capabilities ?? [],
                'current' => $row->isCurrent(),
                'revoked' => $row->revoked_at !== null,
            ])->values(),
            'analytics' => $this->analytics($orgId, $providers->all()),
            'plans' => [
                'chat' => $this->router->plan($orgId, 'chat', false),
                'privateSource' => $this->router->plan($orgId, 'code', true),
            ],
        ]);
    }

    public function storeEvidence(Request $request): RedirectResponse
    {
        $scope = $this->owner($request, true);
        $data = $request->validate([
            'provider_id' => ['required', 'uuid'],
            'model_id' => ['required', 'string', 'max:128'],
            'price_evidence_url' => ['required', 'string', 'max:255', 'url:https'],
            'price_evidence_note' => ['required', 'string', 'min:10', 'max:280'],
            'valid_days' => ['required', 'integer', 'min:1', 'max:'.self::MAX_EVIDENCE_DAYS],
            'data_handling' => ['required', Rule::in(['no-training-documented', 'unknown'])],
            'capabilities' => ['sometimes', 'array', 'max:4'],
            'capabilities.*' => [Rule::in(['chat', 'tools', 'code', 'vision'])],
            'context_limit' => ['nullable', 'integer', 'min:1', 'max:10000000'],
        ]);

        $provider = AiProvider::query()
            ->where('organization_id', $scope['organization_id'])
            ->whereKey($data['provider_id'])
            ->first();
        if ($provider === null) {
            return back()->withErrors(['provider_id' => 'Provider not found.']);
        }

        // Evidence can only describe a model the provider itself listed, and only where the preset
        // has an owner-verified free allowlist. Providers with no free tier can never be unlocked here.
        $tier = $this->manager->presets()[$provider->preset]['free_tier'] ?? 'none';
        if ($tier !== 'allowlist') {
            return back()->withErrors(['model_id' => 'Evidence applies only to allowlist providers; this provider is '.$tier.'.']);
        }
        if (! in_array($data['model_id'], $provider->models_cache ?? [], true)) {
            return back()->withErrors(['model_id' => 'Model not in the last discovery. Run Test connection first.']);
        }

        $now = now();
        AiModelEvidence::query()->updateOrCreate(
            ['ai_provider_id' => $provider->id, 'model_id' => $data['model_id']],
            [
                'organization_id' => $scope['organization_id'],
                'price_evidence_url' => $data['price_evidence_url'],
                'price_evidence_note' => $data['price_evidence_note'],
                'verified_at' => $now,
                'expires_at' => $now->copy()->addDays((int) $data['valid_days']),
                'data_handling' => $data['data_handling'],
                'capabilities' => array_values(array_unique($data['capabilities'] ?? ['chat'])),
                'context_limit' => $data['context_limit'] ?? null,
                'verified_by' => (int) $this->user($request)->id,
                'revoked_at' => null,
            ],
        );

        $this->audit($request, 'model_fabric.evidence_saved', [
            'provider' => $provider->name,
            'model' => $data['model_id'],
            'valid_days' => (int) $data['valid_days'],
            'data_handling' => $data['data_handling'],
        ]);

        return back()->with('status', 'Price evidence saved. The model is routable until it expires or is revoked.');
    }

    public function revokeEvidence(Request $request, string $evidence): RedirectResponse
    {
        $scope = $this->owner($request, true);
        $row = AiModelEvidence::query()
            ->where('organization_id', $scope['organization_id'])
            ->whereKey($evidence)
            ->firstOrFail();
        $row->revoked_at = now();
        $row->save();

        $this->audit($request, 'model_fabric.evidence_revoked', ['model' => $row->model_id]);

        return back()->with('status', 'Evidence revoked. The model is no longer routable.');
    }

    /**
     * Last 24 hours of routed attempts per provider (metadata only).
     *
     * @param  array<int, AiProvider>  $providers
     * @return list<array<string, mixed>>
     */
    private function analytics(string $orgId, array $providers): array
    {
        $rows = AiModelRequest::query()
            ->where('organization_id', $orgId)
            ->where('created_at', '>=', now()->subDay())
            ->orderByDesc('created_at')
            ->limit(5000)
            ->get(['ai_provider_id', 'outcome', 'latency_ms', 'error_code']);

        $out = [];
        foreach ($providers as $provider) {
            $mine = $rows->where('ai_provider_id', $provider->id);
            $ok = $mine->where('outcome', 'ok');
            $latencies = $ok->pluck('latency_ms')->map(fn ($ms): int => (int) $ms)->sort()->values()->all();
            $cooling = ModelFabricGateway::coolingUntil($provider->id);
            $out[] = [
                'provider' => $provider->name,
                'requests' => $mine->count(),
                'ok' => $ok->count(),
                'p50_ms' => $this->percentile($latencies, 50),
                'p95_ms' => $this->percentile($latencies, 95),
                'last_error' => $mine->where('outcome', 'failed')->pluck('error_code')->first(),
                'cooling_until' => $cooling === null ? null : date('c', $cooling),
            ];
        }

        return $out;
    }

    /** @param  list<int>  $sorted */
    private function percentile(array $sorted, int $p): ?int
    {
        if ($sorted === []) {
            return null;
        }

        return $sorted[(int) max(0, ceil(count($sorted) * $p / 100) - 1)];
    }

    /** @return array{organization_id: string, can_manage: bool} */
    private function owner(Request $request, bool $mustManage): array
    {
        $user = $this->user($request);
        $this->access->require($user);
        $scope = $this->scope->for($user);
        abort_if($mustManage && ! $scope['can_manage'], 403);

        return $scope;
    }

    /** @param array<string, mixed> $metadata */
    private function audit(Request $request, string $action, array $metadata): void
    {
        OperatorActionAudit::query()->create([
            'actor_user_id' => (int) $this->user($request)->id,
            'action' => $action,
            'outcome' => 'saved',
            'metadata' => $metadata + ['paid_inference_enabled' => false],
        ]);
    }

    private function user(Request $request): User
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        return $user;
    }
}
