<?php

declare(strict_types=1);

/*
 * AI provider presets. `free_tier` is a policy rule, never a verified balance or billing status:
 *   allowlist    - a free account does NOT make every model free. Inference is admitted only for
 *                  model ids the owner lists as verified-free in `free_models` (empty = blocked)
 *   model-suffix - only models whose id ends with ":free" are admitted
 *   none         - no free tier; blocked while the provider is "free only"
 * Custom endpoints must be on `approved_hosts` (owner-approved, HTTPS, public DNS only).
 */
$csv = static fn (string $name): array => array_values(array_filter(array_map('trim', explode(',', (string) env($name, '')))));

return [
    'presets' => [
        'groq' => ['label' => 'Groq', 'base_url' => 'https://api.groq.com/openai/v1', 'free_tier' => 'allowlist'],
        'openrouter' => ['label' => 'OpenRouter', 'base_url' => 'https://openrouter.ai/api/v1', 'free_tier' => 'model-suffix'],
        'gemini' => ['label' => 'Google Gemini (OpenAI-compatible)', 'base_url' => 'https://generativelanguage.googleapis.com/v1beta/openai', 'free_tier' => 'allowlist'],
        'openai' => ['label' => 'OpenAI', 'base_url' => 'https://api.openai.com/v1', 'free_tier' => 'none'],
        'custom' => ['label' => 'Custom HTTPS endpoint', 'base_url' => null, 'free_tier' => 'none'],
    ],
    'approved_hosts' => $csv('AI_PROVIDER_APPROVED_HOSTS'),
    // Exact model ids the owner has verified as free on the provider's own pricing page.
    'free_models' => [
        'groq' => $csv('AI_PROVIDER_FREE_MODELS_GROQ'),
        'gemini' => $csv('AI_PROVIDER_FREE_MODELS_GEMINI'),
    ],
];
