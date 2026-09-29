<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('kslp_issuer_subscriptions', function (Blueprint $t): void {
            $t->uuid('id')->primary();
            $t->uuid('organization_id')->unique();
            $t->string('tier', 32);
            $t->string('status', 24);
            $t->unsignedInteger('product_limit')->default(1);
            $t->unsignedInteger('monthly_issue_limit')->default(100);
            $t->timestamp('current_period_end')->nullable();
            $t->timestamps();
            $t->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
        });
        Schema::create('kslp_licensed_products', function (Blueprint $t): void {
            $t->uuid('id')->primary();
            $t->uuid('organization_id');
            $t->string('product_code', 96)->unique();
            $t->string('name', 160);
            $t->string('status', 24)->default('active');
            $t->json('default_features')->nullable();
            $t->json('default_limits')->nullable();
            $t->timestamps();
            $t->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $t->index(['organization_id', 'status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('kslp_licensed_products');
        Schema::dropIfExists('kslp_issuer_subscriptions');
    }
};
