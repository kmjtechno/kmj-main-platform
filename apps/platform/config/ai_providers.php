<?php

declare(strict_types=1);

/*
 * AI provider presets. `free_tier` is a policy rule, never a verified balance or billing status:
 *   allowlist    - a free account does NOT make every model free. Inference is admitted only for
 *                  model ids the owner lists as verified-free in `free_models` (empty = blocked)
 *   model-suffix - only models whose id ends with ":free" are admitted
 *   catalog-free - only fixed-endpoint Kilo catalog entries with explicit zero pricing and isFree
 *   none         - no free tier; blocked while the provider is "free only"
 * Custom endpoints must be on `approved_hosts` (owner-approved, HTTPS, public DNS only).
 */
$csv = static fn (string $name): array => array_values(array_filter(array_map('trim', explode(',', (string) env($name, '')))));

return [
    'presets' => [
        'groq' => ['label' => 'Groq', 'base_url' => 'https://api.groq.com/openai/v1', 'free_tier' => 'allowlist'],
        'openrouter' => ['label' => 'OpenRouter', 'base_url' => 'https://openrouter.ai/api/v1', 'free_tier' => 'model-suffix'],
        // Anonymous gateway: no billable credential; public chat only, no NVIDIA trial models.
        'kilo-free' => ['label' => 'Kilo Gateway (keyless)', 'base_url' => 'https://ai-gateway.kilo.ai/api/v1', 'free_tier' => 'catalog-free'],
        // Official anonymous community endpoint: catalog discovery only pending live qualification.
        'horde-anonymous' => ['label' => 'AI Horde (anonymous discovery)', 'base_url' => 'https://oai.aihorde.net/v1', 'free_tier' => 'none'],
        'gemini' => ['label' => 'Google Gemini (OpenAI-compatible)', 'base_url' => 'https://generativelanguage.googleapis.com/v1beta/openai', 'free_tier' => 'allowlist'],
        'cerebras' => ['label' => 'Cerebras', 'base_url' => 'https://api.cerebras.ai/v1', 'free_tier' => 'allowlist'],
        'mistral' => ['label' => 'Mistral', 'base_url' => 'https://api.mistral.ai/v1', 'free_tier' => 'allowlist'],
        'sambanova' => ['label' => 'SambaNova', 'base_url' => 'https://api.sambanova.ai/v1', 'free_tier' => 'allowlist'],
        'huggingface' => ['label' => 'Hugging Face router', 'base_url' => 'https://router.huggingface.co/v1', 'free_tier' => 'allowlist'],
        'nvidia' => ['label' => 'NVIDIA NIM', 'base_url' => 'https://integrate.api.nvidia.com/v1', 'free_tier' => 'allowlist'],
        // GitHub Models retired 2026-07-30. Keep the identifier for historical rows only.
        'github' => ['label' => 'GitHub Models (retired)', 'base_url' => 'https://models.github.ai/inference', 'free_tier' => 'none', 'retired' => true],
        // Discovery-only candidates: upstream account, quota and pricing admission are not yet qualified.
        'zai' => ['label' => 'Z.ai GLM (discovery only)', 'base_url' => 'https://api.z.ai/api/paas/v4', 'free_tier' => 'none'],
        'siliconflow' => ['label' => 'SiliconFlow (discovery only)', 'base_url' => 'https://api.siliconflow.com/v1', 'free_tier' => 'none'],
        'modelscope' => ['label' => 'ModelScope (discovery only)', 'base_url' => 'https://api-inference.modelscope.cn/v1', 'free_tier' => 'none'],
        'anyapi' => ['label' => 'AnyAPI (discovery only)', 'base_url' => 'https://api.anyapi.ai/v1', 'free_tier' => 'none'],
        'llm7' => ['label' => 'LLM7 (discovery only)', 'base_url' => 'https://api.llm7.io/v1', 'free_tier' => 'none'],
        'pollinations' => ['label' => 'Pollinations (discovery only)', 'base_url' => 'https://gen.pollinations.ai/v1', 'free_tier' => 'none'],
        // Connect-only presets never activate inference without explicit zero-cost admission.
        'cohere' => ['label' => 'Cohere (evaluation key)', 'base_url' => 'https://api.cohere.ai/compatibility/v1', 'free_tier' => 'allowlist'],
        'qwen-sg' => ['label' => 'Alibaba Qwen (Singapore)', 'base_url' => 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'free_tier' => 'none'],
        'qwen-us' => ['label' => 'Alibaba Qwen (US)', 'base_url' => 'https://dashscope-us.aliyuncs.com/compatible-mode/v1', 'free_tier' => 'none'],
        'fireworks' => ['label' => 'Fireworks AI', 'base_url' => 'https://api.fireworks.ai/inference/v1', 'free_tier' => 'none'],
        'together' => ['label' => 'Together AI', 'base_url' => 'https://api.together.xyz/v1', 'free_tier' => 'none'],
        'openai' => ['label' => 'OpenAI', 'base_url' => 'https://api.openai.com/v1', 'free_tier' => 'none'],
        'custom' => ['label' => 'Custom HTTPS endpoint', 'base_url' => null, 'free_tier' => 'none'],
    ],
    'approved_hosts' => $csv('AI_PROVIDER_APPROVED_HOSTS'),
    // Exact model ids the owner has verified as free on the provider's own pricing page.
    'free_models' => [
        'groq' => $csv('AI_PROVIDER_FREE_MODELS_GROQ'),
        'gemini' => $csv('AI_PROVIDER_FREE_MODELS_GEMINI'),
        'cerebras' => $csv('AI_PROVIDER_FREE_MODELS_CEREBRAS'),
        'mistral' => $csv('AI_PROVIDER_FREE_MODELS_MISTRAL'),
        'sambanova' => $csv('AI_PROVIDER_FREE_MODELS_SAMBANOVA'),
        'huggingface' => $csv('AI_PROVIDER_FREE_MODELS_HUGGINGFACE'),
        'nvidia' => $csv('AI_PROVIDER_FREE_MODELS_NVIDIA'),
        'cohere' => $csv('AI_PROVIDER_FREE_MODELS_COHERE'),
    ],
];
