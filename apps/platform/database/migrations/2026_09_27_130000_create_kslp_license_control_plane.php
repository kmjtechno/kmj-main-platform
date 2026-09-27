<?php
use Illuminate\Database\Migrations\Migration; use Illuminate\Database\Schema\Blueprint; use Illuminate\Support\Facades\Schema;
return new class extends Migration {
 public function up():void{
  Schema::create("kslp_licenses",function(Blueprint $t):void{$t->uuid("id")->primary();$t->string("customer_id",128);$t->string("product",64);$t->string("plan",32);$t->string("status",24)->default("active");$t->string("trial_subject_hash",64)->nullable()->unique();$t->unsignedBigInteger("sequence")->default(1);$t->timestamp("starts_at");$t->timestamp("expires_at");$t->timestamp("grace_until")->nullable();$t->timestamp("revoked_at")->nullable();$t->timestamps();$t->index(["customer_id","product","status"]);});
  Schema::create("kslp_activations",function(Blueprint $t):void{$t->uuid("id")->primary();$t->uuid("license_id");$t->string("server_identity",160);$t->string("machine_identity_hash",64);$t->string("idempotency_key",128)->unique();$t->timestamp("activated_at");$t->timestamp("deactivated_at")->nullable();$t->timestamps();$t->foreign("license_id")->references("id")->on("kslp_licenses")->restrictOnDelete();$t->index(["license_id","deactivated_at"]);});
  Schema::create("kslp_license_events",function(Blueprint $t):void{$t->bigIncrements("id");$t->uuid("license_id");$t->string("actor_id",128);$t->string("action",64);$t->string("reason",500)->nullable();$t->uuid("correlation_id");$t->json("metadata")->nullable();$t->timestamp("created_at");$t->index(["license_id","created_at"]);});
  Schema::create("kslp_signing_keys",function(Blueprint $t):void{$t->string("kid",128)->primary();$t->string("purpose",32);$t->text("public_key");$t->string("status",24);$t->timestamp("not_before");$t->timestamp("not_after")->nullable();$t->timestamp("revoked_at")->nullable();$t->timestamps();});
 }
 public function down():void{Schema::dropIfExists("kslp_signing_keys");Schema::dropIfExists("kslp_license_events");Schema::dropIfExists("kslp_activations");Schema::dropIfExists("kslp_licenses");}
};
