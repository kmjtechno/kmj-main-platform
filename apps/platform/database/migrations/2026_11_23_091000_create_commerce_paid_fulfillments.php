<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // One confirmed, independently live-verified order buys exactly ONE
        // bounded subscription period. The license is still activated by
        // the separate device-proof and protected signing workflow.
        Schema::create('commerce_paid_fulfillments', function (Blueprint $table): void {
            $table->uuid('commercial_order_id')->primary();
            $table->uuid('organization_id');
            $table->uuid('product_id');
            $table->uuid('plan_id');
            $table->uuid('entitlement_id')->unique();
            $table->uuid('license_id')->unique();
            $table->string('provider', 24);
            $table->string('provider_order_id', 64);
            $table->string('payment_reference', 96);
            $table->timestampTz('period_starts_at');
            $table->timestampTz('period_ends_at');
            $table->string('status', 24)->default('active');
            $table->timestampsTz();

            $table->foreign('commercial_order_id')->references('id')
                ->on('commerce_orders')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')
                ->on('organizations')->restrictOnDelete();
            $table->foreign('product_id')->references('id')
                ->on('products')->restrictOnDelete();
            $table->foreign('plan_id')->references('id')
                ->on('plans')->restrictOnDelete();
            $table->foreign('entitlement_id')->references('id')
                ->on('entitlements')->restrictOnDelete();
            $table->foreign('license_id')->references('id')
                ->on('kslp_licenses')->restrictOnDelete();
            $table->unique(['provider', 'payment_reference']);
            $table->index(['organization_id', 'product_id', 'status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('commerce_paid_fulfillments');
    }
};
