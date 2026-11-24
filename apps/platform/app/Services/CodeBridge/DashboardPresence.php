<?php

namespace App\Services\CodeBridge;

use Illuminate\Support\Facades\Http;
use Throwable;

final class DashboardPresence
{
    /**
     * The caller must derive devices from the authenticated tenant directory,
     * not browser input. This read-only snapshot never authorizes operations.
     *
     * @param array<int, array<string, mixed>> $devices
     * @return array<string, mixed>|null
     */
    public function snapshot(string $tenant, array $devices): ?array
    {
        if (config('codebridge.enabled') !== true || config('codebridge.dashboard_presence_enabled') !== true) {
            return null;
        }
        $token = config('codebridge.dashboard_presence_token');
        $origin = config('services.codebridge_gateway.url');
        if (! is_string($token) || ! preg_match('/\\A[A-Za-z0-9_-]{43,128}\\z/D', $token)
            || ! is_string($origin) || ! preg_match('/\\Ahttp:\\/\\/127\\.0\\.0\\.1:([1-9][0-9]{0,4})\\/?\\z/D', $origin, $port)
            || (int) $port[1] > 65535 || ! self::validId($tenant)) {
            return null;
        }
        $grants = [];
        foreach ($devices as $device) {
            if (($device['pairing_state'] ?? null) !== 'redeemed' || ! self::validId($device['id'] ?? null)) {
                continue;
            }
            foreach ($device['projects'] ?? [] as $project) {
                if (! self::validId($project['id'] ?? null)) {
                    continue;
                }
                $key = $device['id'].'/'.$project['id'];
                $grants[$key] = ['device' => $device['id'], 'project' => $project['id']];
            }
        }
        if ($grants === [] || count($grants) > 100) {
            return null;
        }

        try {
            $response = Http::acceptJson()
                ->withToken($token)
                ->connectTimeout(1)
                ->timeout(2)
                ->withoutRedirecting()
                ->withOptions(['proxy' => ''])
                ->post(rtrim($origin, '/').'/internal/dashboard/presence', [
                    'tenant' => $tenant,
                    'grants' => array_values($grants),
                ]);
            if (! $response->successful() || strlen($response->body()) > 32768) {
                return null;
            }
            $data = $response->json();
            $now = time();
            $observedAt = self::timestamp($data['observedAt'] ?? null);
            if (! is_array($data) || ($data['tenant'] ?? null) !== $tenant
                || $observedAt === null || $observedAt > $now + 1 || $observedAt < $now - 5
                || ! is_array($data['entries'] ?? null) || ! array_is_list($data['entries'])
                || count($data['entries']) !== count($grants)) {
                return null;
            }
            $entries = [];
            foreach ($data['entries'] as $entry) {
                if (! is_array($entry) || ! self::validId($entry['device'] ?? null)
                    || ! self::validId($entry['project'] ?? null)) {
                    return null;
                }
                $key = $entry['device'].'/'.$entry['project'];
                if (! isset($grants[$key]) || isset($entries[$key])
                    || ! in_array($entry['status'] ?? null, ['READY', 'UNKNOWN'], true)) {
                    return null;
                }
                $seen = self::timestamp($entry['lastSeenAt'] ?? null);
                $ready = $entry['status'] === 'READY' && $seen !== null
                    && $seen <= $observedAt && $seen > $now - 30;
                $entries[$key] = $grants[$key] + [
                    'status' => $ready ? 'READY' : 'UNKNOWN',
                    'lastSeenAt' => $ready ? $entry['lastSeenAt'] : null,
                ];
            }

            return ['observedAt' => $data['observedAt'], 'entries' => array_values($entries)];
        } catch (Throwable) {
            return null;
        }
    }

    private static function validId(mixed $value): bool
    {
        return is_string($value) && preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $value) === 1;
    }

    private static function timestamp(mixed $value): ?int
    {
        if (! is_string($value) || ! preg_match('/\\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{3}Z\\z/D', $value)) {
            return null;
        }
        $date = \DateTimeImmutable::createFromFormat('!Y-m-d\\TH:i:s.v\\Z', $value, new \DateTimeZone('UTC'));

        return $date !== false && $date->format('Y-m-d\\TH:i:s.v\\Z') === $value ? $date->getTimestamp() : null;
    }
}
