<?php
use Illuminate\Database\Migrations\Migration;use Illuminate\Database\Schema\Blueprint;use Illuminate\Support\Facades\Schema;
return new class extends Migration{public function up():void{Schema::table("kslp_licenses",function(Blueprint $t):void{$t->uuid("issuer_organization_id")->nullable()->after("customer_id");$t->index(["issuer_organization_id","product","created_at"]);});}public function down():void{Schema::table("kslp_licenses",function(Blueprint $t):void{$t->dropIndex(["issuer_organization_id","product","created_at"]);$t->dropColumn("issuer_organization_id");});}};
