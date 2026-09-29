<?php
declare(strict_types=1);
namespace Illuminate\Support\Facades {
    final class DB {
        public static object $row;
        public static bool $used = false;
        public static function transaction(callable $fn, int $attempts): mixed {return $fn();}
        public static function table(string $table): object {
            return new class {
                public function where(string $key, mixed $value): self {return $this;}
                public function lockForUpdate(): self {return $this;}
                public function first(): object {return DB::$row;}
                public function update(array $values): void {DB::$used = true;}
            };
        }
    }
}
namespace {
    function now(): object {return new class {public function gt(mixed $time): bool {return false;}};}
    require $argv[1];
    use App\Services\Licensing\Kslp\KslpActivationProof;
    use Illuminate\Support\Facades\DB;
    $pair = sodium_crypto_sign_keypair();
    $b64 = fn(string $value): string => rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
    $identity = 'ed25519:'.$b64(sodium_crypto_sign_publickey($pair));
    $nonce = $b64(random_bytes(32));
    $signature = sodium_crypto_sign_detached('KSLP-ACTIVATE-v1|license|'.$nonce, sodium_crypto_sign_secretkey($pair));
    $rawNonce = base64_decode(strtr($nonce, '-_', '+/'));
    $proof = new KslpActivationProof;
    foreach (['', 'x', str_repeat('x', 65), str_repeat('x', 64), $signature] as $sig) {
        DB::$row = (object) ['license_id'=>'license', 'server_identity'=>$identity, 'nonce_hash'=>hash('sha256',$rawNonce), 'expires_at'=>'future', 'used_at'=>null];
        DB::$used = false;
        try {
            $proof->consume('challenge', 'license', $identity, $nonce, $b64($sig));
            if ($sig !== $signature || !DB::$used) {throw new RuntimeException('Invalid proof accepted');}
        } catch (DomainException $e) {
            if ($sig === $signature || DB::$used || $e->getMessage() !== 'KSLP_ACTIVATION_PROOF_INVALID') {throw $e;}
        }
    }
    echo "Activation signature boundary checks: 5 passed (stub database)\n";
}
