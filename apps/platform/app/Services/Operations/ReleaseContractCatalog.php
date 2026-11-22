<?php

declare(strict_types=1);

namespace App\Services\Operations;

use JsonException;

/**
 * Read-only view of the release contracts checked into release/contracts. It only displays what the
 * repository validator (scripts/validate_release_contracts.py) already enforces in CI: it never runs a
 * gate, reads no secret and acts on nothing. A file that does not look valid is listed by name only.
 */
final class ReleaseContractCatalog
{
    private const MAX_BYTES = 8192;

    private const MAX_FILES = 50;

    /**
     * @return array{status: string, contracts: list<array<string, mixed>>, invalid: list<string>}
     */
    public function load(?string $directory = null): array
    {
        $directory ??= (string) config('kmj.release.contracts_path', base_path('../../release/contracts'));
        $real = realpath($directory);
        if ($real === false || ! is_dir($real)) {
            return ['status' => 'unavailable', 'contracts' => [], 'invalid' => []];
        }

        $files = glob($real.'/*.release.contract.json') ?: [];
        sort($files);
        $contracts = [];
        $invalid = [];
        foreach (array_slice($files, 0, self::MAX_FILES) as $file) {
            $name = basename($file);
            $contract = $this->read($file);
            if ($contract === null || $name !== (string) $contract['project'].'.release.contract.json') {
                $invalid[] = $name;

                continue;
            }
            $contracts[] = $contract;
        }

        return ['status' => 'ok', 'contracts' => $contracts, 'invalid' => $invalid];
    }

    /**
     * @return array<string, mixed>|null
     */
    private function read(string $file): ?array
    {
        if (is_link($file) || ! is_file($file) || filesize($file) > self::MAX_BYTES) {
            return null;
        }
        try {
            $data = json_decode((string) file_get_contents($file), true, 8, JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return null;
        }
        if (! is_array($data) || ($data['schema_version'] ?? null) !== 1 || ($data['approval'] ?? null) !== 'owner-passkey') {
            return null;
        }
        $checks = $data['required_checks'] ?? null;
        if (! is_array($checks) || $checks === [] || count($checks) > 20) {
            return null;
        }
        $names = [];
        foreach ($checks as $check) {
            if (! is_string($check) || $check === '') {
                return null;
            }
            $names[] = $check;
        }
        $project = $this->text($data['project'] ?? null);
        $kind = $this->text($data['kind'] ?? null);
        $repository = $this->text($data['repository'] ?? null);
        $dataRisk = $this->text($data['data_risk'] ?? null);
        $signing = $this->text($data['signing'] ?? null);
        $gate = $this->text($this->inner($data['stage'] ?? null, 'gate'));
        $smoke = $this->text($this->inner($data['smoke'] ?? null, 'probe'));
        $health = $this->text($this->inner($data['health'] ?? null, 'probe'));
        $rollback = $this->text($this->inner($data['rollback'] ?? null, 'strategy'));
        if ($project === null || $kind === null || $repository === null || $dataRisk === null || $signing === null
            || $gate === null || $smoke === null || $health === null || $rollback === null) {
            return null;
        }

        return [
            'project' => $project,
            'kind' => $kind,
            'repository' => $repository,
            'required_checks' => $names,
            'stage_gate' => $gate,
            'smoke_probe' => $smoke,
            'health_probe' => $health,
            'rollback_strategy' => $rollback,
            'data_risk' => $dataRisk,
            'approval' => 'owner-passkey',
            'signing' => $signing,
        ];
    }

    private function text(mixed $value): ?string
    {
        return is_string($value) && $value !== '' ? $value : null;
    }

    private function inner(mixed $value, string $key): mixed
    {
        return is_array($value) ? ($value[$key] ?? null) : null;
    }
}
