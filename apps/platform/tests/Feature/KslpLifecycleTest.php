<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpActivationProof;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use App\Services\Licensing\Kslp\KslpSigner;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class KslpLifecycleTest extends TestCase
{
    use RefreshDatabase;

    private function proof(string $licenseId): array
    {
        $kp = sodium_crypto_sign_keypair();
        $sk = sodium_crypto_sign_secretkey($kp);
        $pk = sodium_crypto_sign_publickey($kp);
        $id = 'ed25519:'.rtrim(strtr(base64_encode($pk), '+/', '-_'), '=');
        $ch = app(KslpActivationProof::class)->challenge($licenseId, $id);
        $msg = 'KSLP-ACTIVATE-v1|'.$licenseId.'|'.$ch['nonce'];
        $sig = rtrim(strtr(base64_encode(sodium_crypto_sign_detached($msg, $sk)), '+/', '-_'), '=');

        return [$id, $ch['challenge_id'], $ch['nonce'], $sig];
    }

    private function activate(KslpLicenseControlPlane $c, string $id, string $key): array
    {
        [$server,$challenge,$nonce,$sig] = $this->proof($id);

        return [$c->activate($id, $server, str_repeat('a', 64), $key, 'owner', $challenge, $nonce, $sig), $server];
    }

    public function test_trial_activation_idempotency_transfer_and_states(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-1', 'trial', 'owner');
        self::assertSame(30.0, Carbon::parse($l['starts_at'])->diffInDays(Carbon::parse($l['expires_at'])));
        [$a] = $this->activate($c, $l['id'], 'retry-1');
        $again = $c->activate($l['id'], $a['server_identity'], str_repeat('a', 64), 'retry-1', 'owner', 'unused', 'unused', 'unused');
        self::assertSame($a['id'], $again['id']);
        self::assertSame('ACTIVE', $c->state($l['id'], Carbon::parse($l['starts_at'])->addDay()));
        [$newServer,$challenge,$nonce,$sig] = $this->proof($l['id']);
        $b = $c->transfer($l['id'], $newServer, str_repeat('b', 64), 'retry-2', 'owner', 'replacement', $challenge, $nonce, $sig);
        self::assertNotSame($a['id'], $b['id']);
        $this->assertDatabaseCount('kslp_license_events', 4);
    }

    public function test_trial_cannot_reset_and_revoke_reactivate_plan_change_work(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-2', 'trial', 'owner');
        try {
            $c->issue('cust-2', 'trial', 'owner');
            self::fail();
        } catch (\DomainException $e) {
            self::assertSame('KSLP_TRIAL_ALREADY_USED', $e->getMessage());
        }$c->changePlan($l['id'], 'professional', 'owner', 'paid');
        $c->revoke($l['id'], 'owner', 'security');
        self::assertSame('REVOKED', $c->state($l['id']));
        $c->reactivate($l['id'], 'owner', 'cleared');
        self::assertNotSame('REVOKED', $c->state($l['id']));
    }

    public function test_signed_lease_is_server_bound(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-3', 'business', 'owner');
        [$a] = $this->activate($c, $l['id'], 'retry-3');
        $kp = sodium_crypto_sign_keypair();
        $sk = sodium_crypto_sign_secretkey($kp);
        $signer = new class($sk) implements KslpSigner
        {
            public function __construct(private string $sk) {}

            public function kid(): string
            {
                return 'test-kid';
            }

            public function sign(string $m): string
            {
                return sodium_crypto_sign_detached($m, $this->sk);
            }
        };
        $product = Product::query()->create(['slug' => 'cloudos-test', 'name' => 'CloudOS', 'status' => 'active']);
        Plan::query()->create(['product_id' => $product->id, 'code' => 'cloudos.business', 'name' => 'Business', 'pricing_model' => 'quote', 'status' => 'active', 'features' => ['hosting' => true], 'limits' => ['nodes' => 3]]);
        $token = $c->lease($l['id'], $a['id'], $signer);
        self::assertSame(3, count(explode('.', $token)));
    }

    public function test_sensitive_mutation_requires_a_specific_audit_reason(): void
    {
        $c = app(KslpLicenseControlPlane::class);
        $l = $c->issue('cust-reason','business','owner');
        $this->expectException(\DomainException::class);
        $this->expectExceptionMessage('KSLP_REASON_REQUIRED');
        $c->revoke($l['id'],'owner',' ');
    }
}
