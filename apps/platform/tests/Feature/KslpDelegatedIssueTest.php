<?php
namespace Tests\Feature;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;use App\Services\Licensing\Kslp\KslpLicenseControlPlane;use Illuminate\Foundation\Testing\RefreshDatabase;use KMJ\MainPlatform\Organizations\Models\Organization;use Tests\TestCase;
final class KslpDelegatedIssueTest extends TestCase{use RefreshDatabase;
 public function test_subscribed_vendor_can_issue_server_bound_license_for_own_registered_product():void{$o=Organization::query()->create(["name"=>"Vendor","slug"=>"vendor"]);$a=app(KslpIssuerSubscriptionAuthority::class);$a->subscribe((string)$o->id,"professional");$a->registerProduct((string)$o->id,"VENDOR.APP","Vendor App",["pro"=>true]);$l=app(KslpLicenseControlPlane::class)->issueDelegated((string)$o->id,"customer-1","VENDOR.APP","professional","vendor-admin");self::assertSame("VENDOR.APP",$l["product"]);self::assertSame((string)$o->id,$l["issuer_organization_id"]);$this->assertDatabaseHas("kslp_license_events",["license_id"=>$l["id"],"action"=>"delegated_issued"]);}
}
