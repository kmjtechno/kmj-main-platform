<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('commerce_orders', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->uuid('product_id');
            $table->unsignedBigInteger('requester_user_id');
            $table->string('status', 24)->default('requested');
            $table->string('idempotency_key', 160)->unique();
            $table->char('currency', 3)->nullable();
            $table->unsignedBigInteger('amount_minor')->nullable();
            $table->string('confirmation_reference', 160)->nullable();
            $table->timestampTz('confirmed_at')->nullable();
            $table->timestampTz('cancelled_at')->nullable();
            $table->timestamps();
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('product_id')->references('id')->on('products')->restrictOnDelete();
            $table->foreign('requester_user_id')->references('id')->on('users')->restrictOnDelete();
            $table->index(['organization_id', 'status', 'created_at']);
            $table->index(['product_id', 'status']);
        });

        Schema::create('commerce_ledger', function (Blueprint $table): void {
            $table->bigIncrements('sequence');
            $table->uuid('order_id');
            $table->uuid('organization_id');
            $table->unsignedBigInteger('actor_user_id')->nullable();
            $table->string('event_type', 64);
            $table->json('payload');
            $table->timestampTz('occurred_at');
            $table->timestampTz('created_at')->useCurrent();

            $table->foreign('order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('actor_user_id')->references('id')->on('users')->nullOnDelete();
            $table->index(['organization_id', 'sequence']);
            $table->index(['order_id', 'sequence']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('commerce_ledger');
        Schema::dropIfExists('commerce_orders');
    }
};
