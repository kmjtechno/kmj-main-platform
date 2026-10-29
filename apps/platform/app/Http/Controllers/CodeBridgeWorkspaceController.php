<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\Licensing\CodeBridge\CodeBridgeCustomerDeviceDirectory;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use InvalidArgumentException;

/**
 * Read-only AI workspace shell. It shows ONLY state the Main Platform really owns:
 * the organization's registered devices/projects (never a live heartbeat) and its
 * configured zero-spend AI providers. Conversations, chat execution and job events do not
 * exist in this application, so they are reported as unavailable instead of simulated.
 */
final class CodeBridgeWorkspaceController extends Controller
{
    public function __construct(
        private readonly ResolvesAiProviderScope $scope,
        private readonly ProviderManager $manager,
        private readonly CodeBridgeCustomerDeviceDirectory $devices,
    ) {}

    public function show(Request $request): Response
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $scope = $this->scope->for($user);

        $providers = AiProvider::query()
            ->where('organization_id', $scope['organization_id'])
            ->orderBy('name')->get();

        return Inertia::render('services/codebridge-workspace', [
            'canManage' => $scope['can_manage'],
            'devices' => $this->devices->forTenant((string) $scope['organization_id'], time()),
            'providers' => $providers->map(fn (AiProvider $provider): array => [
                ...$this->manager->present($provider),
                'free_admitted_models' => $this->admittedModels($provider),
            ])->values(),
            // Honest capability map. `false` means no backend exists in this app today.
            'capabilities' => [
                'conversations' => [
                    'available' => false,
                    'reason' => 'Chats run in your connected AI client; Main Platform stores no conversations.',
                ],
                'chat_executor' => [
                    'available' => false,
                    'reason' => 'No Main Platform inference endpoint exists. Free providers are listed for readiness only.',
                ],
                'job_events' => [
                    'available' => false,
                    'reason' => 'Job status lives on the paired device and is read through CodeBridge in your AI client.',
                ],
                'device_pairing' => [
                    'available' => true,
                    'reason' => 'Pairing stays in the Main Platform Control Center.',
                ],
            ],
            'links' => [
                'control_center' => '/services/kmj-codebridge',
                'ai_providers' => '/services/kmj-codebridge/ai-providers',
            ],
        ]);
    }

    /** @return list<string> Models that pass the zero-spend admission guard right now. */
    private function admittedModels(AiProvider $provider): array
    {
        $admitted = [];
        foreach ($provider->models_cache ?? [] as $model) {
            try {
                $this->manager->assertInferenceAllowed($provider, $model);
                $admitted[] = $model;
            } catch (InvalidArgumentException) {
                // Not admitted: disabled, unhealthy, stale discovery or not free.
            }
        }

        return array_slice($admitted, 0, 50);
    }
}
