<?php
namespace KMJ\MainPlatform\Catalog\Services;
use DomainException;
use KMJ\MainPlatform\Catalog\Models\Plan;
final class PlanCatalog {
 public const CLOUDOS_PLANS=[
  "trial"=>["Trial",30], "professional"=>["Professional",0], "business"=>["Business",0],
  "enterprise"=>["Enterprise",0], "custom_oem"=>["Custom/OEM",0],
 ];
 public function ensureCloudOSPlans(string $productId): array {
  $out=[];
  foreach(self::CLOUDOS_PLANS as $code=>[$name,$trialDays]){
   $plan=Plan::query()->firstOrCreate(["code"=>"cloudos.".$code],[
    "product_id"=>$productId,"name"=>$name,"pricing_model"=>$code==="trial"?"trial":"quote",
    "billing_interval"=>null,"currency"=>null,"amount_minor"=>null,"status"=>"active","trial_days"=>$trialDays,
    "features"=>[],"limits"=>[],
   ]);
   if((string)$plan->product_id!==$productId||(string)$plan->name!==$name||(int)$plan->trial_days!==$trialDays) throw new DomainException("Plan conflicts with canonical catalog facts.");
   $out[$code]=$plan;
  }
  return $out;
 }
}
