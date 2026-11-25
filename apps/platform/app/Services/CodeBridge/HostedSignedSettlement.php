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

    /** @return array<string, mixed> */
    public function issueSignerChallenge(User $actor, string $organization, string $device): array
    {
        $this->assertOwner($actor, $organization);
        if (preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $device) !== 1) {
            throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
        }

        return DB::transaction(function () use ($actor, $organization, $device): array {
            $credential = $this->activeCredential($organization, $device);

            return [
                'organization_id' => $organization,
                'device_id' => $device,
                'activation_id' => $credential['activation_id'],
                'credential_id' => $credential['id'],
                'owner_id' => (string) $actor->getKey(),
                'nonce' => bin2hex(random_bytes(32)),
                'expires_at' => time() + 300,
            ];
        }, 3);
    }

    /** @param array<string, mixed> $challenge */
    public function confirmSignerChallenge(User $actor, string $organization, string $device, array $challenge, string $publicKey, string $signature): void
    {
        $this->assertOwner($actor, $organization);
        $bytes = base64_decode($publicKey, true);
        $proof = base64_decode($signature, true);
        if (($challenge['organization_id'] ?? null) !== $organization
            || ($challenge['device_id'] ?? null) !== $device
            || ($challenge['owner_id'] ?? null) !== (string) $actor->getKey()
            || ! is_int($challenge['expires_at'] ?? null) || $challenge['expires_at'] <= time()
            || $challenge['expires_at'] > time() + 300
            || ! is_string($challenge['nonce'] ?? null) || preg_match('/\\A[a-f0-9]{64}\\z/D', $challenge['nonce']) !== 1
            || ! is_string($bytes) || strlen($bytes) !== 32 || base64_encode($bytes) !== $publicKey
            || ! is_string($proof) || strlen($proof) !== 64 || base64_encode($proof) !== $signature) {
            throw new DomainException('CODEBRIDGE_SIGNER_PROOF_DENIED');
        }

        DB::transaction(function () use ($actor, $organization, $device, $challenge, $publicKey, $bytes, $proof): void {
            $credential = $this->activeCredential($organization, $device);
            if (($challenge['activation_id'] ?? null) !== $credential['activation_id']
                || ($challenge['credential_id'] ?? null) !== $credential['id']) {
                throw new DomainException('CODEBRIDGE_SIGNER_PROOF_DENIED');
            }
            $message = implode("\n", [
                'KMJ_CODEBRIDGE_SIGNER_ENROLLMENT_V1',
                $organization,
                $device,
                $credential['activation_id'],
                $credential['id'],
                (string) $actor->getKey(),
                $challenge['nonce'],
                (string) $challenge['expires_at'],
                $publicKey,
                '',
            ]);
            if (! sodium_crypto_sign_verify_detached($proof, $message, $bytes)) {
                throw new DomainException('CODEBRIDGE_SIGNER_PROOF_DENIED');
            }
            $this->pinApprovedSigner($actor, $organization, $device, $publicKey);
        }, 3);
    }

    public function pinApprovedSigner(User $actor, string $organization, string $device, string $publicKey): void
    {
        $this->assertOwner($actor, $organization);
        $bytes = base64_decode($publicKey, true);
        if (strlen($publicKey) !== 44 || ! is_string($bytes) || strlen($bytes) !== 32 || base64_encode($bytes) !== $publicKey) {
            throw new DomainException('CODEBRIDGE_SIGNER_KEY_INVALID');
        }

        DB::transaction(function () use ($organization, $device, $publicKey): void {
            $credential = $this->activeCredential($organization, $device);
            $existing = DB::table('codebridge_receipt_signers')->where('activation_id', $credential['activation_id'])->lockForUpdate()->first();
            if ($existing !== null) {
                if ($existing->credential_id !== $credential['id'] || $existing->public_key !== $publicKey) {
                    throw new DomainException('CODEBRIDGE_SIGNER_ROTATION_REVIEW_REQUIRED');
                }

                return;
            }

            DB::table('codebridge_receipt_signers')->insert([
                'activation_id' => $credential['activation_id'],
                'credential_id' => $credential['id'],
                'public_key' => $publicKey,
                'created_at' => now(),
                'updated_at' => now(),
            ]);
        }, 3);
    }

    /** @return array<string, mixed> */
    public function reserveForOwner(User $actor, string $organization, string $device, string $project, string $execution, string $requestHash, bool $pilotOnly = false): array
    {
        $this->assertOwner($actor, $organization);
        if (! Str::isUuid($execution) || preg_match('/\\A[a-f0-9]{64}\\z/D', $requestHash) !== 1
            || preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $project) !== 1) {
            throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_INVALID');
        }

        return DB::transaction(function () use ($organization, $device, $project, $execution, $requestHash, $pilotOnly): array {
            $credential = $this->activeCredential($organization, $device);
            if (! in_array($credential['plan'], ['community', 'pro'], true)) {
                throw new DomainException('CODEBRIDGE_MONTHLY_PLAN_UNAVAILABLE');
            }
            if (! in_array('read', $this->grants->grantedPermissions($organization, $device, $project), true)) {
                throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
            }
            $signer = DB::table('codebridge_receipt_signers')
                ->where('activation_id', $credential['activation_id'])
                ->where('credential_id', $credential['id'])->first();
            if ($signer === null) {
                throw new DomainException('CODEBRIDGE_SIGNER_NOT_ENROLLED');
            }

            $binding = [
                'organization_id' => $organization,
                'subject_key' => 'account',
                'plan_code' => $credential['plan'],
                'activation_id' => $credential['activation_id'],
                'credential_id' => $credential['id'],
                'device_id' => $device,
                'project_id' => $project,
                'request_sha256' => $requestHash,
                'public_key' => $signer->public_key,
            ];
            $existing = DB::table('codebridge_receipt_bindings')->where('execution_id', $execution)->lockForUpdate()->first();
            if ($existing !== null) {
                if ($pilotOnly || (bool) $existing->pilot_only) {
                    throw new DomainException('CODEBRIDGE_PILOT_DISPATCH_REPLAY');
                }
                foreach ($binding as $key => $value) {
                    if ($existing->{$key} !== $value) {
                        throw new DomainException('CODEBRIDGE_RECEIPT_BINDING_CONFLICT');
                    }
                }
            } else {
                DB::table('codebridge_receipt_bindings')->insert([
                    ...$binding,
                    'execution_id' => $execution,
                    'pilot_only' => $pilotOnly,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            return $this->ledger->reserveTrusted($organization, 'account', $execution, $credential['plan']);
        }, 3);
    }

    /** @return array<string, mixed> */
    public function settleSigned(string $organization, string $execution, string $outcome, string $signature, bool $pilotOnly = false): array
    {
        return DB::transaction(function () use ($organization, $execution, $outcome, $signature, $pilotOnly): array {
            $row = DB::table('codebridge_receipt_bindings')->where('execution_id', $execution)
                ->where('organization_id', $organization)->lockForUpdate()->first();
            if ($row === null || (bool) $row->pilot_only !== $pilotOnly || ($row->outcome !== null && $row->outcome !== $outcome)) {
                throw new DomainException('CODEBRIDGE_RECEIPT_BINDING_CONFLICT');
            }

            $credential = $this->activeCredential($organization, $row->device_id);
            if ($credential['id'] !== $row->credential_id || $credential['activation_id'] !== $row->activation_id
                || $credential['plan'] !== $row->plan_code
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
                ->update(['outcome' => $outcome, 'verified_signature' => $signature, 'updated_at' => now()]);

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

    /** @return array{id: string, activation_id: string, plan: string} */
    private function activeCredential(string $organization, string $device): array
    {
        $row = DB::table('codebridge_device_credentials as c')
            ->join('kslp_activations as a', 'a.id', '=', 'c.activation_id')
            ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
            ->where('c.tenant_id', $organization)->where('c.device_id', $device)
            ->where('l.customer_id', $organization)->where('l.product', 'KMJ_CODEBRIDGE')
            ->whereColumn('a.license_id', 'l.id')->whereNull('a.deactivated_at')
            ->whereNull('c.revoked_at')->where('c.expires_at_epoch', '>', time())
            ->whereExists(static function ($query): void {
                $query->selectRaw('1')->from('codebridge_device_pairings as p')
                    ->whereColumn('p.tenant_id', 'c.tenant_id')
                    ->whereColumn('p.device_id', 'c.device_id')
                    ->whereColumn('p.license_id', 'c.license_id')
                    ->whereColumn('p.activation_id', 'c.activation_id')
                    ->where('p.status', 'consumed')->whereNotNull('p.consumed_at');
            })
            ->where('l.status', 'active')->whereNull('l.revoked_at')
            ->where('l.starts_at', '<=', now())->where('l.expires_at', '>', now())
            ->lockForUpdate()->first(['c.id', 'c.activation_id', 'l.plan']);
        if ($row === null) {
            throw new DomainException('CODEBRIDGE_RECEIPT_SCOPE_DENIED');
        }

        return [
            'id' => (string) $row->id,
            'activation_id' => (string) $row->activation_id,
            'plan' => (string) $row->plan,
        ];
    }
}
