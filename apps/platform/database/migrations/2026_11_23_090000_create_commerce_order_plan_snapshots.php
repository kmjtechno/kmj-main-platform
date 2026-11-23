<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Server-owned commercial facts at checkout, NOT payment/entitlement proof.
        // Reconciliation must compare the captured payment to these exact facts.
        Schema::create('commerce_order_plan_snapshots', function (Blueprint $table): void {
            $table->uuid('commercial_order_id')->primary();
            $table->uuid('organization_id');
            $table->uuid('product_id');
            $table->uuid('plan_id');
            $table->string('plan_code', 96);
            $table->char('currency', 3);
            $table->unsignedBigInteger('amount_minor');
            $table->string('billing_interval', 24);
            $table->timestampsTz();

            $table->foreign('commercial_order_id')->references('id')
                ->on('commerce_orders')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')
                ->on('organizations')->restrictOnDelete();
            $table->foreign('product_id')->references('id')
                ->on('products')->restrictOnDelete();
            $table->foreign('plan_id')->references('id')
                ->on('plans')->restrictOnDelete();
            $table->index(['organization_id', 'plan_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('commerce_order_plan_snapshots');
    }
};
