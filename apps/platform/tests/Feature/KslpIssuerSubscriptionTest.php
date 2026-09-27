<?php
namespace Tests\Feature;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;use Illuminate\Foundation\Testing\RefreshDatabase;use KMJ\MainPlatform\Organizations\Models\Organization;use Tests\TestCase;
final class KslpIssuerSubscriptionTest extends TestCase{use RefreshDatabase;
 public function test_own_product_requires_active_issuer_subscription():void{$o=Organization::query()->create(["name"=>"Vendor","slug"=>"vendor"]);$a=app(KslpIssuerSubscriptionAuthority::class);try{$a->registerProduct((string)$o->id,"VENDOR.APP","Vendor App");self::fail();}catch(\DomainException $e){self::assertSame("KSLP_ISSUER_SUBSCRIPTION_REQUIRED",$e->getMessage());}$a->subscribe((string)$o->id,"professional",5,1000);$p=$a->registerProduct((string)$o->id,"VENDOR.APP","Vendor App",["pro"=>true],["seats"=>10]);self::assertSame("VENDOR.APP",$p["product_code"]);self::assertSame("VENDOR.APP",$a->authorizeIssue((string)$o->id,"VENDOR.APP")["product_code"]);}
}
