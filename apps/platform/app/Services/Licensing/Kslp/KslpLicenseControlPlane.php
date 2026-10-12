<?php

namespace App\Services\Licensing\Kslp;

use Carbon\CarbonInterface;
use DomainException;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

final class KslpLicenseControlPlane
{
    public const PLANS = ['trial', 'professional', 'business', 'enterprise', 'custom_oem'];

    /**
     * @return array<array-key, mixed>
     */
    public function issue(string $customer, string $plan, string $actor, string $reason = ''): array
    {
        if (! in_array($plan, self::PLANS, true)) {
            throw new DomainException('KSLP_INVALID_PLAN');
        }

        return DB::transaction(function () use ($customer, $plan, $actor, $reason) {
            $now = now();
            $trial = $plan === 'trial' ? hash('sha256', $customer.'|KMJ_CLOUDOS') : null;
            if ($trial && DB::table('kslp_licenses')->where('trial_subject_hash', $trial)->exists()) {
                throw new DomainException('KSLP_TRIAL_ALREADY_USED');
            }
            $id = (string) Str::uuid();
            $exp = $plan === 'trial' ? $now->copy()->addDays(30) : $now->copy()->addYear();
            DB::table('kslp_licenses')->insert(['id' => $id, 'customer_id' => $customer, 'product' => 'KMJ_CLOUDOS', 'plan' => $plan, 'status' => 'active', 'trial_subject_hash' => $trial, 'sequence' => 1, 'starts_at' => $now, 'expires_at' => $exp, 'grace_until' => $exp->copy()->addDays(7), 'created_at' => $now, 'updated_at' => $now]);
            $this->event($id, $actor, 'issued', $reason, ['plan' => $plan]);

            return $this->license($id);
        }, 3);
    }

    /**
     * @return array<array-key, mixed>
     */
    public function issueDelegated(string $issuerOrganizationId, string $customer, string $product, string $plan, string $actor, string $reason = ''): array
    {
        if (! in_array($plan, self::PLANS, true)) {
            throw new DomainException('KSLP_INVALID_PLAN');
        }
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->authorizeIssue($issuerOrganizationId, $product);

        return DB::transaction(function () use ($issuerOrganizationId, $customer, $product, $plan, $actor, $reason) {
            $sub = DB::table('kslp_issuer_subscriptions')->where('organization_id', $issuerOrganizationId)->lockForUpdate()->first();
            $used = DB::table('kslp_licenses')->where('issuer_organization_id', $issuerOrganizationId)->where('created_at', '>=', now()->startOfMonth())->count();
            if ($used >= (int) $sub->monthly_issue_limit) {
                throw new DomainException('KSLP_ISSUER_MONTHLY_LIMIT');
            }$now = now();
            $trial = $plan === 'trial' ? hash('sha256', $issuerOrganizationId.'|'.$customer.'|'.$product) : null;
            if ($trial && DB::table('kslp_licenses')->where('trial_subject_hash', $trial)->exists()) {
                throw new DomainException('KSLP_TRIAL_ALREADY_USED');
            }$id = (string) Str::uuid();
            $exp = $plan === 'trial' ? $now->copy()->addDays(30) : $now->copy()->addYear();
            DB::table('kslp_licenses')->insert(['id' => $id, 'customer_id' => $customer, 'issuer_organization_id' => $issuerOrganizationId, 'product' => $product, 'plan' => $plan, 'status' => 'active', 'trial_subject_hash' => $trial, 'sequence' => 1, 'starts_at' => $now, 'expires_at' => $exp, 'grace_until' => $exp->copy()->addDays(7), 'created_at' => $now, 'updated_at' => $now]);
            $this->event($id, $actor, 'delegated_issued', $reason, ['issuer_organization_id' => $issuerOrganizationId, 'product' => $product]);

            return $this->license($id);
        }, 3);
    }

    /**
     * @return array<array-key, mixed>
     */
    public function activate(string $licenseId, string $serverIdentity, string $machineHash, string $idempotencyKey, string $actor, string $challengeId, string $nonce, string $proof): array
    {
        $existing = DB::table('kslp_activations')->where('idempotency_key', $idempotencyKey)->first();
        if ($existing) {
            return $this->matchingActivation($existing, $licenseId, $serverIdentity, $machineHash);
        }app(KslpActivationProof::class)->consume($challengeId, $licenseId, $serverIdentity, $nonce, $proof);

        return DB::transaction(function () use ($licenseId, $serverIdentity, $machineHash, $idempotencyKey, $actor) {
            $existing = DB::table('kslp_activations')->where('idempotency_key', $idempotencyKey)->first();
            if ($existing) {
                return $this->matchingActivation($existing, $licenseId, $serverIdentity, $machineHash);
            }
            $lic = DB::table('kslp_licenses')->where('id', $licenseId)->lockForUpdate()->first();
            if (! $lic) {
                throw new DomainException('KSLP_LICENSE_NOT_FOUND');
            }if ($lic->revoked_at) {
                throw new DomainException('KSLP_REVOKED');
            }
            $active = DB::table('kslp_activations')->where('license_id', $licenseId)->whereNull('deactivated_at')->first();
            if ($active) {
                KslpActivationReplayGuard::requireMatch((array) $active, $licenseId, $serverIdentity, $machineHash);

                return (array) $active;
            }$id = (string) Str::uuid();
            $now = now();
            DB::table('kslp_activations')->insert(['id' => $id, 'license_id' => $licenseId, 'server_identity' => $serverIdentity, 'machine_identity_hash' => $machineHash, 'idempotency_key' => $idempotencyKey, 'activated_at' => $now, 'created_at' => $now, 'updated_at' => $now]);
            $this->event($licenseId, $actor, 'activated', null, ['activation_id' => $id]);

            return (array) DB::table('kslp_activations')->where('id', $id)->first();
        }, 3);
    }

    /**
     * Match idempotency retries to the original license and device, and deny
     * replay after transfer or revocation.
     *
     * @return array<array-key, mixed>
     */
    private function matchingActivation(object $activation, string $licenseId, string $serverIdentity, string $machineHash): array
    {
        $record = (array) $activation;
        KslpActivationReplayGuard::requireMatch($record, $licenseId, $serverIdentity, $machineHash);

        $license = DB::table('kslp_licenses')->where('id', $licenseId)->first(['revoked_at']);
        if ($license === null) {
            throw new DomainException('KSLP_LICENSE_NOT_FOUND');
        }
        if ($license->revoked_at !== null) {
            throw new DomainException('KSLP_REVOKED');
        }

        return (array) $activation;
    }

    /**
     * @return array<array-key, mixed>
     */
    public function changePlan(string $id, string $plan, string $actor, string $reason): array
    {
        if (! in_array($plan, self::PLANS, true) || $plan === 'trial') {
            throw new DomainException('KSLP_INVALID_PLAN');
        }

        return $this->mutate($id, $actor, 'plan_changed', $reason, function ($q) use ($plan) {
            $q->update(['plan' => $plan, 'sequence' => DB::raw('sequence+1'), 'updated_at' => now()]);
        });
    }

    /**
     * @return array<array-key, mixed>
     */
    public function renew(string $id, Carbon $expires, string $actor, string $reason): array
    {
        return $this->mutate($id, $actor, 'renewed', $reason, function ($q) use ($expires) {
            $q->update(['expires_at' => $expires, 'grace_until' => $expires->copy()->addDays(7), 'status' => 'active', 'sequence' => DB::raw('sequence+1'), 'updated_at' => now()]);
        });
    }

    /**
     * @return array<array-key, mixed>
     */
    public function revoke(string $id, string $actor, string $reason): array
    {
        return $this->mutate($id, $actor, 'revoked', $reason, fn ($q) => $q->update(['status' => 'revoked', 'revoked_at' => now(), 'sequence' => DB::raw('sequence+1'), 'updated_at' => now()]));
    }

    /**
     * @return array<array-key, mixed>
     */
    public function reactivate(string $id, string $actor, string $reason): array
    {
        return $this->mutate($id, $actor, 'reactivated', $reason, fn ($q) => $q->update(['status' => 'active', 'revoked_at' => null, 'sequence' => DB::raw('sequence+1'), 'updated_at' => now()]));
    }

    /**
     * @return array<array-key, mixed>
     */
    public function transfer(string $id, string $server, string $machine, string $key, string $actor, string $reason, string $challengeId, string $nonce, string $proof): array
    {
        $this->requireReason($reason);

        return DB::transaction(function () use ($id, $server, $machine, $key, $actor, $reason, $challengeId, $nonce, $proof) {
            DB::table('kslp_activations')->where('license_id', $id)->whereNull('deactivated_at')->update(['deactivated_at' => now(), 'updated_at' => now()]);
            $this->event($id, $actor, 'transferred', $reason);

            return $this->activate($id, $server, $machine, $key, $actor, $challengeId, $nonce, $proof);
        }, 3);
    }

    public function state(string $id, ?CarbonInterface $at = null): string
    {
        $l = $this->license($id);
        $at ??= now();
        if ($l['revoked_at']) {
            return 'REVOKED';
        }if ($at->lte(Carbon::parse($l['expires_at']))) {
            return $at->gte(Carbon::parse($l['expires_at'])->subDays(7)) ? 'RENEWAL_DUE' : 'ACTIVE';
        }if ($l['grace_until'] && $at->lte(Carbon::parse($l['grace_until']))) {
            return 'GRACE';
        }

        return 'RESTRICTED';
    }

    public function lease(string $id, string $activationId, KslpSigner $signer, ?CarbonInterface $now = null): string
    {
        $now ??= now();
        $l = $this->license($id);
        $state = $this->state($id, $now);
        if (in_array($state, ['REVOKED', 'RESTRICTED'], true)) {
            throw new DomainException('KSLP_LICENSE_NOT_LEASABLE');
        }$a = (array) DB::table('kslp_activations')->where('id', $activationId)->where('license_id', $id)->whereNull('deactivated_at')->first();
        if (! $a) {
            throw new DomainException('KSLP_ACTIVATION_CONFLICT');
        }[$features,$limits] = app(KslpEntitlementResolver::class)->resolve($l);
        $claims = ['protocol_version' => 'KSLP-v1', 'license_id' => $id, 'customer_id' => $l['customer_id'], 'product' => $l['product'], 'plan' => $l['plan'], 'server_identity' => $a['server_identity'], 'activation_id' => $activationId, 'features' => $features, 'limits' => $limits, 'iat' => $now->getTimestamp(), 'nbf' => $now->getTimestamp() - 5, 'exp' => min($now->copy()->addHours(24)->getTimestamp(), Carbon::parse($l['grace_until'] ?? $l['expires_at'])->timestamp), 'sequence' => (int) $l['sequence'], 'nonce' => Str::random(32), 'kid' => $signer->kid(), 'jti' => (string) Str::uuid(), 'aud' => 'kmj-cloudos', 'grace_until' => $l['grace_until'] ? Carbon::parse($l['grace_until'])->timestamp : null];

        return KslpCodec::encode($claims, $signer->kid(), fn ($m) => $signer->sign($m));
    }

    /**
     * @return array<array-key, mixed>
     */
    private function mutate(string $id, string $actor, string $action, string $reason, callable $fn): array
    {
        $this->requireReason($reason);

        return DB::transaction(function () use ($id, $actor, $action, $reason, $fn) {
            $q = DB::table('kslp_licenses')->where('id', $id);
            if (! $q->lockForUpdate()->exists()) {
                throw new DomainException('KSLP_LICENSE_NOT_FOUND');
            }$fn($q);
            $this->event($id, $actor, $action, $reason);

            return $this->license($id);
        }, 3);
    }

    private function requireReason(string $reason): void
    {
        if (strlen(trim($reason)) < 3) {
            throw new DomainException('KSLP_REASON_REQUIRED');
        }
    }

    /**
     * @return array<array-key, mixed>
     */
    private function license(string $id): array
    {
        $x = DB::table('kslp_licenses')->where('id', $id)->first();
        if (! $x) {
            throw new DomainException('KSLP_LICENSE_NOT_FOUND');
        }

        return (array) $x;
    }

    /**
     * @param  array<array-key, mixed>  $meta
     */
    private function event(string $id, string $actor, string $action, ?string $reason, array $meta = []): void
    {
        DB::table('kslp_license_events')->insert(['license_id' => $id, 'actor_id' => $actor, 'action' => $action, 'reason' => $reason, 'correlation_id' => (string) Str::uuid(), 'metadata' => $meta ? json_encode($meta) : null, 'created_at' => now()]);
    }
}
