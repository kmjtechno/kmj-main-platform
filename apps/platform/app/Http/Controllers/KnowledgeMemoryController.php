<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\AiProviders\ResolvesAiProviderScope;
use App\Services\KnowledgeMemory\KnowledgeMemoryStore;
use DomainException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;
use InvalidArgumentException;

final class KnowledgeMemoryController extends Controller
{
    public function __construct(
        private readonly ResolvesAiProviderScope $scope,
        private readonly KnowledgeMemoryStore $memory,
    ) {}

    public function index(Request $request): JsonResponse
    {
        $organizationId = $this->organization($request);
        $validated = $request->validate([
            'query' => ['required', 'string', 'max:80', 'regex:/\A[a-zA-Z0-9][a-zA-Z0-9 .:-]{0,79}\z/D'],
            'limit' => ['sometimes', 'integer', 'min:1', 'max:20'],
        ]);

        return $this->privateJson([
            'project' => $this->project(),
            'observations' => $this->memory->search(
                $organizationId,
                $this->project(),
                $validated['query'],
                (int) ($validated['limit'] ?? 10),
            ),
            'authority' => 'untrusted_historical_knowledge',
        ]);
    }

    public function show(Request $request, string $observation): JsonResponse
    {
        $organizationId = $this->organization($request);
        $row = $this->memory->get($organizationId, $this->project(), $observation);
        abort_if($row === null, 404);

        return $this->privateJson([
            'observation' => $row,
            'authority' => 'untrusted_historical_knowledge',
        ]);
    }

    public function store(Request $request): JsonResponse
    {
        $organizationId = $this->organization($request, true);
        $input = $request->validate([
            'operation_id' => ['required', 'string', 'min:8', 'max:96', 'regex:/\A[A-Za-z0-9][A-Za-z0-9._:-]{7,95}\z/D'],
            'topic_key' => ['required', 'string', 'max:96', 'regex:/\A[a-z][a-z0-9-]{0,23}\/[a-z0-9][a-z0-9._-]{0,63}\z/D'],
            'type' => ['required', Rule::in(['decision', 'bugfix', 'architecture', 'discovery', 'pattern', 'policy', 'summary'])],
            'title' => ['required', 'string', 'min:1', 'max:160'],
            'content' => ['required', 'string', 'min:1', 'max:4096'],
            'expected_revision' => ['required', 'integer', 'min:0', 'max:1000000'],
        ]);

        try {
            $result = $this->memory->save($organizationId, $this->project(), $input);
        } catch (DomainException $error) {
            // A stale revision or mismatched retry never silently overwrites.
            return $this->privateJson(['error' => $error->getMessage()], 409);
        } catch (InvalidArgumentException) {
            // Never reflect rejected text or credentials into errors/logs.
            throw ValidationException::withMessages(['content' => 'Invalid or potentially sensitive memory input.']);
        }

        return $this->privateJson($result, $result['replayed'] ? 200 : 201);
    }

    private function organization(Request $request, bool $write = false): string
    {
        abort_unless(config('knowledge_memory.enabled') === true, 404);

        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $scope = $this->scope->for($user);
        if ($write) {
            abort_unless($scope['can_manage'] === true, 403);
        }

        // Organization is derived exclusively from the existing authenticated,
        // membership-backed active CodeBridge entitlement. Never read scope
        // from route, headers, request body or an AI-supplied project label.
        return $scope['organization_id'];
    }

    private function project(): string
    {
        return 'kmj-codebridge';
    }

    /** @param array<string, mixed> $payload */
    private function privateJson(array $payload, int $status = 200): JsonResponse
    {
        return response()->json($payload, $status)->header('Cache-Control', 'private, no-store');
    }
}
