<?php

declare(strict_types=1);

/*
 * AI provider presets. `free_tier` is what the provider documents, not a verified balance:
 *   plan         - a free plan with rate limits exists (billing status is never verified here)
 *   model-suffix - only models whose id ends with ":free" are free
 *   none         - no free tier; blocked while the provider is "free only"
 * Custom endpoints must be on `approved_hosts` (owner-approved, HTTPS, public DNS only).
 */
return [
    'presets' => [
        'groq' => ['label' => 'Groq', 'base_url' => 'https://api.groq.com/openai/v1', 'free_tier' => 'plan'],
        'openrouter' => ['label' => 'OpenRouter', 'base_url' => 'https://openrouter.ai/api/v1', 'free_tier' => 'model-suffix'],
        'gemini' => ['label' => 'Google Gemini (OpenAI-compatible)', 'base_url' => 'https://generativelanguage.googleapis.com/v1beta/openai', 'free_tier' => 'plan'],
        'openai' => ['label' => 'OpenAI', 'base_url' => 'https://api.openai.com/v1', 'free_tier' => 'none'],
        'custom' => ['label' => 'Custom HTTPS endpoint', 'base_url' => null, 'free_tier' => 'none'],
    ],
    'approved_hosts' => array_values(array_filter(array_map(
        'trim',
        explode(',', (string) env('AI_PROVIDER_APPROVED_HOSTS', '')),
    ))),
];
