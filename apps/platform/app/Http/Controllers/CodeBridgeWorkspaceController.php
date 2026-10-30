<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiProvider;
use App\Models\User;
use App\Services\AiProviders\ProviderManager;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\CodeBridge\Workspace\WorkspaceChatService;
use App\Services\CodeBridge\Workspace\WorkspaceConversation;
use App\Services\CodeBridge\Workspace\WorkspaceJobService;
use App\Services\CodeBridge\Workspace\WorkspaceToolCatalog;
use App\Services\Licensing\CodeBridge\CodeBridgeCustomerDeviceDirectory;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Inertia;
use Inertia\Response;
use InvalidArgumentException;
use RuntimeException;

/**
 * AI workspace. It shows ONLY state the Main Platform really owns: registered devices/projects
 * (never a live heartbeat), configured zero-spend AI providers, and persistent conversations
 * answered by admitted free models. Device job/tool events live on the paired device and are
 * reported as unavailable instead of simulated.
 */
final class CodeBridgeWorkspaceController extends Controller
{
    public function __construct(
        private readonly ResolvesAiProviderScope $scope,
        private readonly ProviderManager $manager,
        private readonly CodeBridgeCustomerDeviceDirectory $devices,
        private readonly WorkspaceChatService $chat,
        private readonly WorkspaceJobService $jobs,
    ) {}

    public function show(Request $request): Response
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $scope = $this->scope->for($user);
        $tenant = (string) $scope['organization_id'];
        $devices = $this->devices->forTenant($tenant, time());

        // Selection is validated against the tenant's own paired projects; anything else is ignored.
        $deviceId = (string) $request->query('device', '');
        $projectId = (string) $request->query('project', '');
        $selected = $this->chat->projectAuthorized($tenant, $deviceId, $projectId)
            ? ['device_id' => $deviceId, 'project_id' => $projectId] : null;
        $active = null;
        $transcript = ['messages' => [], 'events' => []];
        if ($selected !== null && is_string($request->query('c')) && $request->query('c') !== '') {
            $conversation = $this->chat->conversation($tenant, (int) $user->id, (string) $request->query('c'));
            if ($conversation->deviceId === $deviceId && $conversation->projectId === $projectId) {
                $active = ['id' => $conversation->id, 'title' => $conversation->title];
                $transcript = $this->chat->transcript($conversation);
            }
        }

        $jobList = $selected === null ? [] : $this->jobs->list($tenant, (int) $user->id, $deviceId, $projectId);
        $jobId = (string) $request->query('j', '');
        $jobEvents = [];
        $activeJobId = null;
        if ($selected !== null && $jobId !== '' && Str::isUlid($jobId) && collect($jobList)->contains('id', $jobId)) {
            $jobEvents = $this->jobs->events($tenant, (int) $user->id, $jobId);
            $activeJobId = $jobId;
        }

        $providers = AiProvider::query()
            ->where('organization_id', $tenant)
            ->orderBy('name')->get();

        return Inertia::render('services/codebridge-workspace', [
            'canManage' => $scope['can_manage'],
            'devices' => $devices,
            'selected' => $selected,
            'conversations' => $selected === null ? [] : $this->chat->conversations($tenant, (int) $user->id, $deviceId, $projectId),
            'activeConversation' => $active,
            'transcript' => $transcript,
            'chatError' => session('chat_error'),
            'jobs' => $jobList,
            'jobEvents' => $jobEvents,
            'activeJobId' => $activeJobId,
            'tools' => WorkspaceToolCatalog::all(),
            'providers' => $providers->map(fn (AiProvider $provider): array => [
                ...$this->manager->present($provider),
                'free_admitted_models' => $this->admittedModels($provider),
            ])->values(),
            // Honest capability map. `false` means no backend exists in this app today.
            'capabilities' => [
                'conversations' => [
                    'available' => true,
                    'reason' => 'Conversations are stored per organization, user and paired project.',
                ],
                'chat_executor' => [
                    'available' => $providers->contains(fn (AiProvider $p): bool => $this->admittedModels($p) !== []),
                    'reason' => 'Needs an enabled, healthy free provider with an admitted model. Add one in AI providers.',
                ],
                'job_events' => [
                    'available' => WorkspaceJobService::enabled(),
                    'reason' => WorkspaceJobService::enabled()
                        ? 'Approved named tools are queued for the paired device. A request only runs once a device agent claims it; unclaimed requests expire.'
                        : 'Device tool requests are switched off on this server. Job status stays on the paired device and is read through CodeBridge in your AI client.',
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

    public function runTool(Request $request): RedirectResponse
    {
        [$user, $tenant] = $this->actor($request);
        $data = $request->validate([
            'device_id' => ['required', 'string', 'max:64'],
            'project_id' => ['required', 'string', 'max:64'],
            'tool' => ['required', 'string', 'max:40'],
            'gate' => ['nullable', 'string', 'max:40'],
            'idempotency_key' => ['required', 'string', 'max:64'],
        ]);
        $arguments = isset($data['gate']) && $data['gate'] !== '' ? ['gate' => $data['gate']] : [];
        try {
            $result = $this->jobs->enqueue($tenant, (int) $user->id, $data['device_id'], $data['project_id'], $data['tool'], $arguments, $data['idempotency_key']);
        } catch (InvalidArgumentException|RuntimeException $exception) {
            session()->flash('chat_error', $exception->getMessage());

            return $this->toJob($data['device_id'], $data['project_id'], null);
        }

        return $this->toJob($data['device_id'], $data['project_id'], $result['id']);
    }

    public function cancelTool(Request $request, string $job): RedirectResponse
    {
        [$user, $tenant] = $this->actor($request);
        $row = DB::table('codebridge_workspace_jobs')->where('id', $job)->where('tenant_id', $tenant)->where('user_id', (int) $user->id)->first(['device_id', 'project_id']);
        abort_if($row === null, 404);
        $this->jobs->cancel($tenant, (int) $user->id, $job);
        $fields = (array) $row;

        return $this->toJob((string) $fields['device_id'], (string) $fields['project_id'], $job);
    }

    public function start(Request $request): RedirectResponse
    {
        [$user, $tenant] = $this->actor($request);
        $data = $request->validate([
            'device_id' => ['required', 'string', 'max:64'],
            'project_id' => ['required', 'string', 'max:64'],
            'title' => ['nullable', 'string', 'max:120'],
        ]);
        $id = $this->chat->createConversation($tenant, (int) $user->id, $data['device_id'], $data['project_id'], (string) ($data['title'] ?? ''));

        return $this->to($data['device_id'], $data['project_id'], $id);
    }

    public function send(Request $request, string $conversation): RedirectResponse
    {
        return $this->act($request, $conversation, function (WorkspaceConversation $row, array $data): void {
            $this->chat->send($row, $data['content'], $data['provider_id'], $data['model']);
        }, true);
    }

    public function retry(Request $request, string $conversation, string $message): RedirectResponse
    {
        return $this->act($request, $conversation, function (WorkspaceConversation $row, array $data) use ($message): void {
            $this->chat->retry($row, $message, $data['provider_id'], $data['model']);
        }, false);
    }

    public function cancel(Request $request, string $conversation, string $message): RedirectResponse
    {
        [$user, $tenant] = $this->actor($request);
        $row = $this->chat->conversation($tenant, (int) $user->id, $conversation);
        try {
            $this->chat->cancel($row, $message);
        } catch (RuntimeException $exception) {
            session()->flash('chat_error', $exception->getMessage());
        }

        return $this->to($row->deviceId, $row->projectId, $row->id);
    }

    /**
     * @param  callable(WorkspaceConversation, array<string, string>): void  $work
     */
    private function act(Request $request, string $conversation, callable $work, bool $needsContent): RedirectResponse
    {
        [$user, $tenant] = $this->actor($request);
        $row = $this->chat->conversation($tenant, (int) $user->id, $conversation);
        $data = $request->validate([
            'content' => [$needsContent ? 'required' : 'nullable', 'string', 'max:4000'],
            'provider_id' => ['required', 'string', 'max:64'],
            'model' => ['required', 'string', 'regex:/\A[A-Za-z0-9._:\/-]{1,128}\z/'],
        ]);
        try {
            $work($row, $data);
        } catch (RuntimeException $exception) {
            session()->flash('chat_error', $exception->getMessage());
        }

        return $this->to($row->deviceId, $row->projectId, $row->id);
    }

    /** @return array{0: User, 1: string} */
    private function actor(Request $request): array
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);

        return [$user, (string) $this->scope->for($user)['organization_id']];
    }

    private function to(string $deviceId, string $projectId, string $conversationId): RedirectResponse
    {
        return redirect()->route('codebridge.workspace', ['device' => $deviceId, 'project' => $projectId, 'c' => $conversationId]);
    }

    private function toJob(string $deviceId, string $projectId, ?string $jobId): RedirectResponse
    {
        return redirect()->route('codebridge.workspace', array_filter(['device' => $deviceId, 'project' => $projectId, 'j' => $jobId]));
    }

    /** @return list<string> Models that pass the zero-spend admission guard right now. */
    private function admittedModels(AiProvider $provider): array
    {
        $admitted = [];
        foreach ($provider->models_cache ?? [] as $model) {
            try {
                $this->manager->assertInferenceAllowed($provider, $model);
                $admitted[] = $model;
            } catch (InvalidArgumentException|RuntimeException) {
                // Not admitted: disabled, unhealthy, stale discovery or not free.
            }
        }

        return array_slice($admitted, 0, 50);
    }
}
