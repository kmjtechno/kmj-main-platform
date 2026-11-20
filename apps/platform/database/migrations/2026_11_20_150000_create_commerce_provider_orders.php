<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Binds a commercial order to the provider order created for it. The amount here is
        // the server-owned expected amount; provider evidence must equal it before confirmation.
        Schema::create('commerce_provider_orders', function (Blueprint $table): void {
            $table->id();
            $table->uuid('commercial_order_id');
            $table->string('provider', 24);
            $table->string('provider_order_id', 64);
            $table->unsignedBigInteger('amount_minor');
            $table->char('currency', 3);
            $table->string('environment', 16)->default('sandbox');
            $table->timestampsTz();

            $table->foreign('commercial_order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->unique(['provider', 'provider_order_id']);
            $table->unique(['commercial_order_id', 'provider']);
        });

        Schema::table('payment_webhook_events', function (Blueprint $table): void {
            $table->string('processing_note', 64)->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('payment_webhook_events', function (Blueprint $table): void {
            $table->dropColumn('processing_note');
        });
        Schema::dropIfExists('commerce_provider_orders');
    }
};
