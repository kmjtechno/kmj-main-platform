<?php

namespace App\Services\Licensing\CodeBridge;

use Illuminate\Support\Facades\DB;

final class CodeBridgeCustomerDeviceDirectory
{
    /**
     * List only the authenticated organization's registered, unexpired devices.
     *
     * The Main Platform stores enrollment and grants, NOT the live gateway
     * heartbeat. Never convert registration into an invented Online status.
     *
     * @return array<int, array<string, mixed>>
     */
    public function forTenant(string $tenantId, int $now, int $limit = 100): array
    {
        $limit = max(1, min(100, $limit));

        $rows = DB::table('codebridge_device_credentials as c')
            ->leftJoin('codebridge_device_pairings as p', function ($join): void {
                $join->on('p.activation_id', '=', 'c.activation_id')
                    ->on('p.tenant_id', '=', 'c.tenant_id');
            })
            ->where('c.tenant_id', $tenantId)
            ->whereNull('c.revoked_at')
            ->where('c.expires_at_epoch', '>', $now)
            ->orderBy('c.device_id')
            ->limit($limit)
            ->get([
                'c.device_id',
                'p.device_name',
                'p.platform',
                'p.arch',
                'p.project_id',
                'p.project_name',
                'p.consumed_at',
            ]);

        return $rows->map(static function (object $row): array {
            $projectId = is_string($row->project_id) && $row->project_id !== ''
                ? $row->project_id : null;

            return [
                'id' => (string) $row->device_id,
                'name' => is_string($row->device_name) && $row->device_name !== ''
                    ? $row->device_name : (string) $row->device_id,
                'platform' => is_string($row->platform) ? $row->platform : null,
                'arch' => is_string($row->arch) ? $row->arch : null,
                'projects' => $projectId === null ? [] : [[
                    'id' => $projectId,
                    'name' => is_string($row->project_name) && $row->project_name !== ''
                        ? $row->project_name : $projectId,
                ]],
                'registered_at' => $row->consumed_at,
                'registration' => 'registered',
                'connection_status' => 'not_verified',
            ];
        })->all();
    }
}
