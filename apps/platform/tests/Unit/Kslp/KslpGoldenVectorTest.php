<?php
namespace Tests\Unit\Kslp;
use App\Services\Licensing\Kslp\KslpVerifier;
use Tests\TestCase;
final class KslpGoldenVectorTest extends TestCase {
 public function test_canonical_golden_vector():void {
  $v=json_decode(file_get_contents(base_path("../../contracts/kslp-v1/golden-vector-001.json")),true,512,JSON_THROW_ON_ERROR);
  $pk=base64_decode($v["public_key_b64"],true);
  $claims=(new KslpVerifier())->verify($v["token"],fn($kid)=>$pk,$v["server_identity"],$v["now"],$v["expected_product"]);
  self::assertSame($v["expected_claims"],$claims);
 }
}
