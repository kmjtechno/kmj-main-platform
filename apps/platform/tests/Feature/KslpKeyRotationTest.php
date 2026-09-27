<?php
namespace Tests\Feature;
use App\Services\Licensing\Kslp\KslpKeyRegistry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;
final class KslpKeyRotationTest extends TestCase {
 use RefreshDatabase;
 public function test_key_domains_rotation_and_revocation_are_separate():void {
  $r=app(KslpKeyRegistry::class);
  $r->publish("lic-1","license","pub1"); $r->publish("lic-2","license","pub2","retiring");
  $r->publish("rel-1","release","relpub"); $r->publish("ev-1","evidence","evpub");
  self::assertCount(2,$r->discovery("license")); self::assertCount(1,$r->discovery("release")); self::assertCount(1,$r->discovery("evidence"));
  $r->revoke("lic-1"); self::assertCount(1,$r->discovery("license"));
 }
}
