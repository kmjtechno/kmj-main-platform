<?php
namespace App\Services\Licensing\Kslp;
use DomainException; use Illuminate\Support\Facades\DB;
final class KslpKeyRegistry {
 public const PURPOSES=["license","release","evidence"];
 public function publish(string $kid,string $purpose,string $publicKey,string $status="active"):void{
  if(!in_array($purpose,self::PURPOSES,true))throw new DomainException("KSLP_INVALID_KEY_PURPOSE");
  if($publicKey==="")throw new DomainException("KSLP_INVALID_PUBLIC_KEY");
  DB::table("kslp_signing_keys")->updateOrInsert(["kid"=>$kid],["purpose"=>$purpose,"public_key"=>$publicKey,"status"=>$status,"not_before"=>now(),"updated_at"=>now(),"created_at"=>now()]);
 }
 public function revoke(string $kid):void{if(DB::table("kslp_signing_keys")->where("kid",$kid)->update(["status"=>"revoked","revoked_at"=>now(),"updated_at"=>now()])!==1)throw new DomainException("KSLP_UNKNOWN_KID");}
 public function discovery(string $purpose):array{return DB::table("kslp_signing_keys")->where("purpose",$purpose)->whereIn("status",["active","retiring"])->whereNull("revoked_at")->orderBy("not_before")->get(["kid","purpose","public_key","status","not_before","not_after"])->map(fn($x)=>(array)$x)->all();}
 public function publicKey(string $kid,string $purpose):string{$x=DB::table("kslp_signing_keys")->where("kid",$kid)->where("purpose",$purpose)->whereIn("status",["active","retiring"])->whereNull("revoked_at")->first();if(!$x)throw new DomainException("KSLP_UNKNOWN_KID");return (string)$x->public_key;}
}
