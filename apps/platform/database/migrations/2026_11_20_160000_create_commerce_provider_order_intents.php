<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Durable provider-create reservation, committed before external HTTP.
        // Never store an API secret or an unverified provider response here.
        Schema::create('commerce_provider_order_intents', function (Blueprint $table): void {
            $table->id();
            $table->uuid('commercial_order_id');
            $table->string('provider', 24);
            $table->unsignedBigInteger('amount_minor');
            $table->char('currency', 3);
            $table->string('creation_status', 24)->default('creating');
            $table->timestampsTz();

            $table->foreign('commercial_order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->unique(['commercial_order_id', 'provider']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('commerce_provider_order_intents');
    }
};
