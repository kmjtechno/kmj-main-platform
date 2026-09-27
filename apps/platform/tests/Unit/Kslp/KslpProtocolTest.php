<?php
namespace Tests\Unit\Kslp;
use App\Services\Licensing\Kslp\KslpCodec;
use App\Services\Licensing\Kslp\KslpVerifier;
use DomainException;
use PHPUnit\Framework\TestCase;
final class KslpProtocolTest extends TestCase {
    private function claims(int $now): array { return ["protocol_version"=>"KSLP-v1","license_id"=>"lic-00000001","customer_id"=>"cust-1","product"=>"KMJ_CLOUDOS","plan"=>"trial","server_identity"=>"ed25519:server_identity_0000000001","activation_id"=>"act-00000001","features"=>["hosting"=>true],"limits"=>["nodes"=>1],"iat"=>$now,"nbf"=>$now-1,"exp"=>$now+3600,"sequence"=>1,"nonce"=>"nonce-0000000000001","kid"=>"lic-test-1","jti"=>"jti-00000001","aud"=>"kmj-cloudos","grace_until"=>$now+7200]; }
    public function test_valid_and_tampered_server_and_expiry_fail_closed(): void {
        $now=1800000000; $kp=sodium_crypto_sign_keypair(); $sk=sodium_crypto_sign_secretkey($kp); $pk=sodium_crypto_sign_publickey($kp);
        $token=KslpCodec::encode($this->claims($now),"lic-test-1",fn($m)=>sodium_crypto_sign_detached($m,$sk));
        $v=new KslpVerifier(); self::assertSame("trial",$v->verify($token,fn($kid)=>$pk,"ed25519:server_identity_0000000001",$now)["plan"]);
        foreach([["ed25519:other_server_identity_00001",$now,"KSLP_SERVER_MISMATCH"],["ed25519:server_identity_0000000001",$now+4000,"KSLP_EXPIRED"]] as [$server,$time,$error]) {
            try {$v->verify($token,fn($kid)=>$pk,$server,$time); self::fail("accepted invalid token");} catch(DomainException $e){self::assertSame($error,$e->getMessage());}
        }
        $parts=explode(".",$token); $parts[1][5]=$parts[1][5]==="A"?"B":"A";
        $this->expectException(DomainException::class); $v->verify(implode(".",$parts),fn($kid)=>$pk,"ed25519:server_identity_0000000001",$now);
    }
}
