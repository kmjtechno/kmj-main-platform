<?php

namespace App\Services\Licensing;

use Closure;
use JsonException;
use Symfony\Component\Process\Process;
use Throwable;

final class RustSandboxLicenseVerifier
{
    /**
     * @param  Closure(string, string, float): array{exit_code: int, output: string}|null  $runner
     */
    public function __construct(
        private readonly string $binaryPath,
        private readonly string $secret,
        private readonly float $timeoutSeconds = 5.0,
        private readonly ?Closure $runner = null,
    ) {}

    /**
     * @return array{valid: bool, reason: string|null, claims: array<string, mixed>|null}
     */
    public function validate(string $license): array
    {
        if (trim($this->binaryPath) === '' || trim($this->secret) === '') {
            return $this->invalid('verifier_unconfigured');
        }

        try {
            $result = $this->runner instanceof Closure
                ? ($this->runner)($license, $this->secret, $this->timeoutSeconds)
                : $this->runProcess($license);
        } catch (Throwable) {
            return $this->invalid('verifier_failed');
        }

        if ($result['exit_code'] !== 0) {
            return $this->invalid('verifier_failed');
        }

        try {
            $decoded = json_decode($result['output'], true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return $this->invalid('verifier_invalid_response');
        }

        if (! is_array($decoded) || ! array_key_exists('valid', $decoded) || ! is_bool($decoded['valid'])) {
            return $this->invalid('verifier_invalid_response');
        }

        $reason = $decoded['reason'] ?? null;
        $claims = $decoded['claims'] ?? null;

        if (($reason !== null && ! is_string($reason)) || ($claims !== null && ! is_array($claims))) {
            return $this->invalid('verifier_invalid_response');
        }

        if ($decoded['valid'] === true && ($reason !== null || $claims === null)) {
            return $this->invalid('verifier_invalid_response');
        }

        if ($decoded['valid'] === false && (! is_string($reason) || trim($reason) === '' || $claims !== null)) {
            return $this->invalid('verifier_invalid_response');
        }

        return [
            'valid' => $decoded['valid'],
            'reason' => $reason,
            'claims' => $claims,
        ];
    }

    /**
     * @return array{exit_code: int, output: string}
     */
    private function runProcess(string $license): array
    {
        $process = new Process([$this->binaryPath], null, [
            'KMJ_SANDBOX_LICENSE_SECRET' => $this->secret,
        ]);
        $process->setTimeout($this->timeoutSeconds);
        $process->setInput(json_encode(['license' => $license], JSON_THROW_ON_ERROR));
        $process->run();

        return [
            'exit_code' => $process->getExitCode() ?? 1,
            'output' => $process->getOutput(),
        ];
    }

    /**
     * @return array{valid: false, reason: string, claims: null}
     */
    private function invalid(string $reason): array
    {
        return [
            'valid' => false,
            'reason' => $reason,
            'claims' => null,
        ];
    }
}
