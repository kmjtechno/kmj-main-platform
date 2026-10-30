<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\Workspace;

use InvalidArgumentException;

/**
 * The ONLY tools the workspace may request from a paired device. Each entry is a fixed,
 * named, administrator-configurable operation with a closed argument schema and the
 * device permission it needs. There is no free-form command, path or shell argument, and
 * the device agent must still enforce its own policy before running anything.
 */
final class WorkspaceToolCatalog
{
    /** @var array<string, array{label: string, permission: string, description: string}> */
    private const TOOLS = [
        'git_status' => ['label' => 'Git status', 'permission' => 'read', 'description' => 'Read-only repository status of the paired project.'],
        'inspect_project' => ['label' => 'Inspect project', 'permission' => 'read', 'description' => 'Read-only project summary reported by the device.'],
        'quality_gate' => ['label' => 'Run quality gate', 'permission' => 'execute', 'description' => 'Runs one administrator-configured gate by id on the device.'],
    ];

    private const GATE_ID = '/\A[a-z][a-z0-9_-]{0,39}\z/';

    /** @return list<array{name: string, label: string, permission: string, description: string}> */
    public static function all(): array
    {
        $out = [];
        foreach (self::TOOLS as $name => $tool) {
            $out[] = ['name' => $name, ...$tool];
        }

        return $out;
    }

    public static function permission(string $tool): string
    {
        return self::TOOLS[$tool]['permission'] ?? throw new InvalidArgumentException('unknown_tool');
    }

    /**
     * @param  array<mixed>  $arguments
     * @return array<string, string>
     */
    public static function validate(string $tool, array $arguments): array
    {
        if (! isset(self::TOOLS[$tool])) {
            throw new InvalidArgumentException('unknown_tool');
        }
        if ($tool !== 'quality_gate') {
            if ($arguments !== []) {
                throw new InvalidArgumentException('unexpected_arguments');
            }

            return [];
        }
        $gate = $arguments['gate'] ?? null;
        if (count($arguments) !== 1 || ! is_string($gate) || preg_match(self::GATE_ID, $gate) !== 1) {
            throw new InvalidArgumentException('invalid_gate');
        }

        return ['gate' => $gate];
    }
}
