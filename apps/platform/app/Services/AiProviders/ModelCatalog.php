<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

/**
 * Heuristic capability hint by model family name. This is routing PREFERENCE only. It never makes a
 * model eligible: eligibility is decided solely by verified-zero evidence (ModelFabricRouter).
 * Tier 3 = frontier-class open or large models, 2 = strong mid-size, 1 = small or unknown.
 */
final class ModelCatalog
{
    private const TIER3 = '/(kimi-k\d|glm-?[5-9]|deepseek-(v[3-9]|r1)|minimax-m[2-9]|qwen3(\.\d+)?-(max|coder|235b|397b|480b|next)|gpt-oss-120b|nemotron-3(\.\d+)?-(ultra|super)|gemini-[\d.]+-pro|devstral|llama-?3\.1-405b|mistral-large|claude)/i';

    private const TIER2 = '/(qwen3|qwen2\.5-coder-(32|72)b|gpt-oss-20b|llama-?3\.3-70b|llama-?4|gemini-[\d.]+-flash|mistral-medium|codestral|glm-?4|gemma-?\d*-?(27|31)b|nemotron|deepseek|command-a|kimi|minimax|mixtral)/i';

    private const CODING = '/(coder|codestral|devstral|-code|code-)/i';

    /** @return array{tier: int, coding: bool} */
    public function info(string $model): array
    {
        $tier = preg_match(self::TIER3, $model) === 1 ? 3 : (preg_match(self::TIER2, $model) === 1 ? 2 : 1);

        return ['tier' => $tier, 'coding' => preg_match(self::CODING, $model) === 1];
    }
}
