<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

/**
 * Rule-based task classification. It never calls a model (no extra cost or latency): published
 * router research reports that simple rules capture much of the saving of trained routers.
 * Profiles: simple (short chat), coding (normal code work), complex (large or agentic code work).
 */
final class TaskProfiler
{
    public const SIMPLE = 'simple';

    public const CODING = 'coding';

    public const COMPLEX = 'complex';

    /** @param  list<array{role: string, content: string}>  $messages */
    public function classify(array $messages, string $capability = 'chat'): string
    {
        $text = '';
        foreach ($messages as $message) {
            $text .= "\n".$message['content'];
        }
        $length = strlen($text);
        $fences = substr_count($text, '```');
        $codeSignals = preg_match_all('/\b(refactor|implement|debug|stack trace|traceback|exception|compile|unit test|migration|regex|algorithm|function|class|interface|segfault|cmake|namespace)\b|\.(php|tsx?|jsx?|rs|cpp|hpp|py|go|java|cs)\b/i', $text);
        $agentic = preg_match('/\b(multi-?file|across the (repo|codebase)|architecture|design a system|rewrite|end-to-end|migrate)\b/i', $text) === 1;

        if ($capability === 'tools' || $agentic || $length > 12000 || $fences >= 6) {
            return self::COMPLEX;
        }
        if ($capability === 'code' || $fences >= 2 || (int) $codeSignals >= 3 || ($length > 1500 && (int) $codeSignals >= 1)) {
            return self::CODING;
        }

        return self::SIMPLE;
    }
}
