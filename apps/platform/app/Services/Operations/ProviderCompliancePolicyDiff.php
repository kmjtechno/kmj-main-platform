<?php

namespace App\Services\Operations;

final class ProviderCompliancePolicyDiff
{
    /**
     * @param  array<string, mixed>  $previous
     * @param  array<string, mixed>  $current
     * @return array{
     *     status: 'unchanged'|'changed',
     *     review_required: bool,
     *     legal_interpretation: false,
     *     changes: array<int, string>
     * }
     */
    public function compare(array $previous, array $current): array
    {
        $changes = [];

        foreach (['provider_id', 'policy_version'] as $field) {
            if (($previous[$field] ?? null) !== ($current[$field] ?? null)) {
                $changes[] = $field;
            }
        }

        $changes = [
            ...$changes,
            ...$this->changedEntries(
                (array) ($previous['sources'] ?? []),
                (array) ($current['sources'] ?? []),
                'id',
                'source',
            ),
            ...$this->changedEntries(
                (array) ($previous['rules'] ?? []),
                (array) ($current['rules'] ?? []),
                'code',
                'rule',
            ),
        ];

        $changes = array_values(array_unique($changes));
        sort($changes);

        return [
            'status' => $changes === [] ? 'unchanged' : 'changed',
            'review_required' => $changes !== [],
            'legal_interpretation' => false,
            'changes' => $changes,
        ];
    }

    /**
     * @param  array<int|string, mixed>  $previous
     * @param  array<int|string, mixed>  $current
     * @return array<int, string>
     */
    private function changedEntries(
        array $previous,
        array $current,
        string $identityKey,
        string $prefix,
    ): array {
        $before = $this->indexByIdentity($previous, $identityKey);
        $after = $this->indexByIdentity($current, $identityKey);
        $identities = array_values(array_unique([
            ...array_keys($before),
            ...array_keys($after),
        ]));
        sort($identities);

        $changes = [];

        foreach ($identities as $identity) {
            if (($before[$identity] ?? null) !== ($after[$identity] ?? null)) {
                $changes[] = $prefix.':'.$identity;
            }
        }

        return $changes;
    }

    /**
     * @param  array<int|string, mixed>  $entries
     * @return array<string, array<string, mixed>>
     */
    private function indexByIdentity(array $entries, string $identityKey): array
    {
        $indexed = [];

        foreach ($entries as $entry) {
            if (! is_array($entry)) {
                continue;
            }

            $identity = $entry[$identityKey] ?? null;
            if (! is_string($identity) || $identity === '') {
                continue;
            }

            ksort($entry);
            $indexed[$identity] = $entry;
        }

        ksort($indexed);

        return $indexed;
    }
}
