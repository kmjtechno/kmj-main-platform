<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Models\User;
use App\Services\CodeBridge\Workspace\WorkspaceJobService;
use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Internal transactional signed-settlement adapter. No HTTP route or billing
 * activation. A trusted operator must separately approve signer enrollment.
 * Only organization-owner account plans are supported; paid seats require
 * a dedicated signed assignment authority and are intentionally denied.
 */
final class HostedSignedSettlement
{
    public function __construct(
        private readonly MonthlyHostedUsageLedger $ledger,
        private readonly HostedExecutionReceiptVerifier $verifier,
        private readonly OrganizationDirectory $organizations,
        private readonly WorkspaceJobService $grants,
    ) {}

    public function pinApprovedSigner(User $actor, string $organization, string $device, string $publicKey): void
    {
        $this->assertOwner($actor, $organization);
        $bytes = base64_decode($publicKey, true);
        if (strlen($publicKey) !== 44 || ! is_string($bytes) || strlen($bytes) !== 32 || base64_encode($bytes) !== $publicKey) {
            throw new DomainException('CODEBRIDGE_SIGNER_KEY_INVALID');
        }

        DB::transaction(function () use ($organization, $device, $publicKey): void {
            $credential = $this->activeCredential($organization, $device);
            $existing = DB::table('codebridge_receipt_signers')->where('activation_id', $credential->activation_id)->lockForUpdate()->first();
            if ($existing !== null) {
                if ($existing->credential_id !== $credential->id || $existing->public_key !== $publicKey) {
                    throw new DomainException('CODEBRIDGE_SIGNER_ROTATION_REVIEW_REQUIRED');
                }

                return;
            }

            DB::table('codebridge_receipt_signers')->insert([
                'activation_id' => $credential->activation_id,
                'credential_id' => $credential->id,
                'public_key' => $publicKey,
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        }, 3);
    }

    /** @return array<string, mixed> */
    public function reserveForOwner(User $actor, string $organization, string $device, string $project, string $execution, string $requestHash): array
    {
        $this->assertOwner($actor, $organization);
        if (! Str::isUuid($execution) || preg_match('/\\A[a-f0-9]{64}\\z/D', $requestHash) !== 1
            || preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $project) !== 1) {
            throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_INVALID');
        }

        return DB::transaction(function () use ($organization, $device, $project, $execution, $requestHash): array {
            $credential = $this->activeCredential($organization, $device);
            if (! in_array($credential->plan, ['community', 'pro'], true)) {
                throw new DomainException('CODEBRIDGE_MONTHLY_PLAN_UNAVAILABLE');
            }
            if (! in_array('read', $this->grants->grantedPermissions($organization, $device, $project), true)) {
                throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
            }
            $signer = DB::table('codebridge_receipt_signers')
                ->where('activation_id', $credential->activation_id)
                ->where('credential_id', $credential->id)->first();
            if ($signer === null) {
                throw new DomainException('CODEBRIDGE_SIGNER_NOT_ENROLLED');
            }

            $binding = [
                'organization_id' => $organization,
                'subject_key' => 'account',
                'plan_code' => $credential->plan,
                'activation_id' => $credential->activation_id,
                'credential_id' => $credential->id,
                'device_id' => $device,
                'project_id' => $project,
                'request_sha256' => $requestHash,
                'public_key' => $signer->public_key,
            ];
            $existing = DB::table('codebridge_receipt_bindings')->where('execution_id', $execution)->lockForUpdate()->first();
            if ($existing !== null) {
                foreach ($binding as $key => $value) {
                    if ($existing->{$key} !== $value) {
                        throw new DomainException('CODEBRIDGE_RECEIPT_BINDING_CONFLICT');
                    }
                }
            } else {
                DB::table('codebridge_receipt_bindings')->insert([
                    ...$binding,
                    'execution_id' => $execution,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            return $this->ledger->reserveTrusted($organization, 'account', $execution, $credential->plan);
        }, 3);
    }

    /** @return array<string, mixed> */
    public function settleSigned(string $organization, string $execution, string $outcome, string $signature): array
    {
        return DB::transaction(function () use ($organization, $execution, $outcome, $signature): array {
            $row = DB::table('codebridge_receipt_bindings')->where('execution_id', $execution)
                ->where('organization_id', $organization)->lockForUpdate()->first();
            if ($row === null || ($row->outcome !== null && $row->outcome !== $outcome)) {
                throw new DomainException('CODEBRIDGE_RECEIPT_BINDING_CONFLICT');
            }

            $credential = $this->activeCredential($organization, $row->device_id);
            if ($credential->id !== $row->credential_id || $credential->activation_id !== $row->activation_id
                || $credential->plan !== $row->plan_code
                || ! in_array('read', $this->grants->grantedPermissions($organization, $row->device_id, $row->project_id), true)) {
                throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
            }

            $expected = [
                'organization_id' => $organization,
                'subject_key' => $row->subject_key,
                'execution_id' => $execution,
                'device_id' => $row->device_id,
                'project_id' => $row->project_id,
                'request_sha256' => $row->request_sha256,
                'outcome' => $outcome,
            ];
            if (! $this->verifier->verifyTrusted($expected, $signature, $row->public_key)) {
                throw new DomainException('CODEBRIDGE_MONTHLY_COMPLETION_PROOF_REQUIRED');
            }

            $result = $this->ledger->completeTrusted($organization, $row->subject_key, $execution, true);
            DB::table('codebridge_receipt_bindings')->where('execution_id', $execution)
                ->update(['outcome' => $outcome, 'updated_at' => now()]);

            return $result;
        }, 3);
    }

    private function assertOwner(User $actor, string $organization): void
    {
        if (! $actor->exists || $actor->email_verified_at === null || ! Str::isUuid($organization)
            || ! $this->organizations->userCanManage((int) $actor->getKey(), $organization)) {
            throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
        }
    }

    private function activeCredential(string $organization, string $device): object
    {
        $row = DB::table('codebridge_device_credentials as c')
            ->join('kslp_activations as a', 'a.id', '=', 'c.activation_id')
            ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
            ->where('c.tenant_id', $organization)->where('c.device_id', $device)
            ->where('l.customer_id', $organization)->where('l.product', 'KMJ_CODEBRIDGE')
            ->whereColumn('a.license_id', 'l.id')->whereNull('a.deactivated_at')
            ->whereNull('c.revoked_at')->where('c.expires_at_epoch', '>', time())
            ->where('l.status', 'active')->whereNull('l.revoked_at')
            ->where('l.starts_at', '<=', now())->where('l.expires_at', '>', now())
            ->lockForUpdate()->first(['c.id', 'c.activation_id', 'l.plan']);
        if ($row === null) {
            throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
        }

        return $row;
    }
}
