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

/**
 * OpenAI-compatible surface over the verified-zero gateway (non-streaming). It never names a provider
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
        $plan = $this->router->plan($token->organization_id, 'chat', $token->private_source);

        return response()->json([
            'object' => 'list',
            'data' => [['id' => 'modelfabric-auto', 'object' => 'model', 'owned_by' => 'kmj-modelfabric']],
            'modelfabric' => ['status' => $plan['status'], 'routes' => count($plan['routes'])],
        ]);
    }

    public function chat(Request $request): JsonResponse
    {
        $token = $this->token($request);
        $data = $request->validate([
            'messages' => ['required', 'array', 'min:1', 'max:'.self::MAX_MESSAGES],
            'messages.*.role' => ['required', Rule::in(['system', 'user', 'assistant'])],
            'messages.*.content' => ['required', 'string', 'max:'.self::MAX_CHARS],
            'stream' => ['sometimes', 'boolean'],
            'model' => ['sometimes', 'nullable', 'string', 'max:128'],
        ]);
        if (! empty($data['stream'])) {
            return $this->error(400, 'streaming_not_supported', 'Streaming is not supported yet; send stream=false.');
        }
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
        $result = $this->gateway->complete($token->organization_id, $messages, $capability, $token->private_source);
        if (! $result['ok']) {
            $code = (string) $result['error_code'];

            return $this->error($code === ModelFabricRouter::NO_ROUTE ? 503 : 502, $code, 'No verified-zero route could answer this request.');
        }

        return response()->json([
            'id' => 'chatcmpl-mf-'.Str::lower(Str::random(24)),
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
