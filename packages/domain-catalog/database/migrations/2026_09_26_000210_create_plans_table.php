<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
return new class extends Migration {
 public function up(): void { Schema::create("plans",function(Blueprint $table):void{
  $table->uuid("id")->primary(); $table->uuid("product_id"); $table->string("code",96)->unique(); $table->string("name",160);
  $table->string("pricing_model",24); $table->string("billing_interval",24)->nullable(); $table->char("currency",3)->nullable();
  $table->unsignedBigInteger("amount_minor")->nullable(); $table->string("status",24)->default("active"); $table->unsignedSmallInteger("trial_days")->default(0);
  $table->json("features")->nullable(); $table->json("limits")->nullable(); $table->timestamps();
  $table->foreign("product_id")->references("id")->on("products")->restrictOnDelete(); $table->index(["product_id","status"]);
 }); }
 public function down(): void { Schema::dropIfExists("plans"); }
};
