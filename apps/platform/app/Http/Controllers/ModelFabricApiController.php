<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\AiModelToken;
use App\Services\AiProviders\ModelFabricGateway;
use App\Services\AiProviders\ModelFabricRouter;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Symfony\Component\HttpFoundation\StreamedResponse;

/**
 * OpenAI-compatible surface over the verified-zero gateway (streaming is replayed after routing completes). It never names a provider
 * or model from the caller: routing is decided by ModelFabric alone, and when nothing qualifies the
 * answer is NO_FREE_ROUTE_AVAILABLE. Prompts and answers are never logged.
 */
final class ModelFabricApiController extends Controller
{
    private const MAX_MESSAGES = 64;

    private const MAX_CHARS = 200000;

    public function __construct(
        private readonly ModelFabricGateway $gateway,
        private readonly ModelFabricRouter $router,
    ) {}

    public function models(Request $request): JsonResponse
    {
        $token = $this->token($request);
        $capability = $token->private_source ? 'code' : 'chat';
        $plan = $this->router->plan($token->organization_id, $capability, $token->private_source);

        return response()->json([
            'object' => 'list',
            'data' => [['id' => 'modelfabric-auto', 'object' => 'model', 'owned_by' => 'kmj-modelfabric']],
            'modelfabric' => [
                'status' => $plan['status'],
                'routes' => count($plan['routes']),
                // Derived from the authenticated token, never a client claim.
                // Counts describe planning only, not available quota or an invoice.
                'scope' => $token->private_source ? 'private-source-coding' : 'general-chat',
                'free_routes' => count(array_filter($plan['routes'], static fn (array $route): bool => ($route['cost_class'] ?? null) === 'free')),
            ],
        ]);
    }

    public function chat(Request $request): JsonResponse|StreamedResponse
    {
        $token = $this->token($request);
        // Unsupported controls must not be silently discarded before a paid-or-free
        // upstream request. In particular, tools and output limits change semantics.
        if (array_diff(array_keys($request->all()), ['messages', 'stream', 'model']) !== []) {
            return $this->error(400, 'unsupported_parameter', 'Only text chat messages, model and stream are supported.');
        }
        $data = $request->validate([
            'messages' => ['required', 'array', 'min:1', 'max:'.self::MAX_MESSAGES],
            'messages.*' => ['required', 'array:role,content'],
            'messages.*.role' => ['required', Rule::in(['system', 'user', 'assistant'])],
            'messages.*.content' => ['required', 'string', 'max:'.self::MAX_CHARS],
            'stream' => ['sometimes', 'boolean'],
            'model' => ['sometimes', 'nullable', 'string', 'max:128'],
        ]);
        $messages = [];
        $chars = 0;
        foreach ($data['messages'] as $message) {
            $chars += strlen((string) $message['content']);
            $messages[] = ['role' => (string) $message['role'], 'content' => (string) $message['content']];
        }
        if ($chars > self::MAX_CHARS) {
            return $this->error(413, 'request_too_large', 'Conversation is too large.');
        }

        // The caller's "model" field is ignored on purpose: it cannot pick a paid or unverified model.
        $capability = $token->private_source ? 'code' : 'chat';
        $result = $this->gateway->complete($token->organization_id, $messages, $capability, $token->private_source, $this->sessionKey($request));
        if (! $result['ok']) {
            $code = (string) $result['error_code'];

            return $this->error($code === ModelFabricRouter::NO_ROUTE ? 503 : 502, $code, 'No verified-zero route could answer this request.');
        }

        $id = 'chatcmpl-mf-'.Str::lower(Str::random(24));
        if (! empty($data['stream'])) {
            return $this->sse($id, (string) $result['model'], (string) $result['content']);
        }

        return response()->json([
            'id' => $id,
            'object' => 'chat.completion',
            'created' => time(),
            'model' => (string) $result['model'],
            'choices' => [[
                'index' => 0,
                'message' => ['role' => 'assistant', 'content' => (string) $result['content']],
                'finish_reason' => 'stop',
            ]],
            'modelfabric' => ['provider' => $result['provider'], 'attempts' => $result['attempts'], 'profile' => $result['profile']],
        ]);
    }

    /**
     * Compatibility streaming: routing, admission and caps run to completion first (an error is still a normal
     * JSON error), then the verified answer is replayed as OpenAI-style chunks. No provider is called while streaming.
     */
    private function sse(string $id, string $model, string $content): StreamedResponse
    {
        $created = time();
        $chunk = static fn (array $delta, ?string $finish): string => 'data: '.json_encode([
            'id' => $id,
            'object' => 'chat.completion.chunk',
            'created' => $created,
            'model' => $model,
            'choices' => [['index' => 0, 'delta' => $delta, 'finish_reason' => $finish]],
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)."\n\n";

        return response()->stream(function () use ($chunk, $content): void {
            echo $chunk(['role' => 'assistant', 'content' => ''], null);
            foreach (mb_str_split($content, 48) ?: [] as $piece) {
                echo $chunk(['content' => $piece], null);
            }
            echo $chunk([], 'stop');
            echo "data: [DONE]\n\n";
        }, 200, [
            'Content-Type' => 'text/event-stream',
            'Cache-Control' => 'no-cache',
            'X-Accel-Buffering' => 'no',
        ]);
    }

    /** Optional opaque conversation id; it only biases ordering among already-admitted routes. */
    private function sessionKey(Request $request): ?string
    {
        $key = trim((string) $request->header('X-ModelFabric-Session'));

        return preg_match('/^[A-Za-z0-9._:-]{1,64}$/', $key) === 1 ? $key : null;
    }

    private function token(Request $request): AiModelToken
    {
        $token = $request->attributes->get('modelfabric_token');
        abort_unless($token instanceof AiModelToken, 401);

        return $token;
    }

    private function error(int $status, string $code, string $message): JsonResponse
    {
        return response()->json(['error' => ['message' => $message, 'type' => 'modelfabric_error', 'code' => $code]], $status);
    }
}
