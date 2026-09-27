<?php
namespace App\Services\Licensing\Kslp;
use DomainException;use Illuminate\Support\Facades\DB;
final class KslpEntitlementResolver{
 public function resolve(array $license):array{
  if($license["product"]==="KMJ_CLOUDOS"){$p=DB::table("plans")->where("code","cloudos.".$license["plan"])->where("status","active")->first();if(!$p)throw new DomainException("KSLP_ENTITLEMENT_POLICY_NOT_CONFIGURED");$features=json_decode((string)($p->features??"[]"),true)?:[];$limits=json_decode((string)($p->limits??"[]"),true)?:[];}
  else{$p=DB::table("kslp_licensed_products")->where("product_code",$license["product"])->where("organization_id",$license["issuer_organization_id"]??null)->where("status","active")->first();if(!$p)throw new DomainException("KSLP_ENTITLEMENT_POLICY_NOT_CONFIGURED");$features=json_decode((string)($p->default_features??"[]"),true)?:[];$limits=json_decode((string)($p->default_limits??"[]"),true)?:[];}
  if($features===[]&&$limits===[])throw new DomainException("KSLP_ENTITLEMENT_POLICY_NOT_CONFIGURED");return [$features,$limits];
 }
}
