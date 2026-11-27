<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // An owner-reviewed order snapshot, NOT a pricebook, checkout or
        // settlement authority. One immutable binding per commercial order.
        Schema::create('kslp_commercial_order_terms', function (Blueprint $table): void {
            $table->uuid('commercial_order_id')->primary();
            $table->uuid('issuer_organization_id');
            $table->uuid('licensed_product_id');
            $table->uuid('catalog_product_id');
            $table->string('catalog_slug', 160);
            $table->string('licensed_product_code', 96);
            $table->char('currency', 3);
            $table->unsignedBigInteger('amount_minor');
            $table->unsignedBigInteger('approved_by_user_id');
            $table->timestampTz('created_at')->useCurrent();

            $table->foreign('commercial_order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->foreign('issuer_organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('licensed_product_id')->references('id')->on('kslp_licensed_products')->restrictOnDelete();
            $table->foreign('catalog_product_id')->references('id')->on('products')->restrictOnDelete();
            $table->foreign('approved_by_user_id')->references('id')->on('users')->restrictOnDelete();
            $table->index(['issuer_organization_id', 'licensed_product_id'], 'kslp_order_terms_scope');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('kslp_commercial_order_terms');
    }
};
