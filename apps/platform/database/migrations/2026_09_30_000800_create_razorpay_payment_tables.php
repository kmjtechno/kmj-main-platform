<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('razorpay_payment_attempts', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('order_id');
            $table->uuid('organization_id');
            $table->uuid('product_id');
            $table->uuid('plan_id');
            $table->unsignedBigInteger('requester_user_id');
            $table->string('idempotency_key', 160)->unique();
            $table->string('receipt', 40)->unique();
            $table->string('provider_order_id', 80)->nullable()->unique();
            $table->string('provider_payment_id', 80)->nullable()->unique();
            $table->char('currency', 3);
            $table->unsignedBigInteger('amount_minor');
            $table->string('status', 32)->default('initiating')->index();
            $table->string('failure_code', 64)->nullable();
            $table->unsignedBigInteger('refunded_amount_minor')->default(0);
            $table->timestampTz('captured_at')->nullable();
            $table->timestampTz('refunded_at')->nullable();
            $table->timestamps();

            $table->foreign('order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('product_id')->references('id')->on('products')->restrictOnDelete();
            $table->foreign('plan_id')->references('id')->on('plans')->restrictOnDelete();
            $table->foreign('requester_user_id')->references('id')->on('users')->restrictOnDelete();
            $table->index(['organization_id', 'status', 'created_at']);
        });

        Schema::create('razorpay_webhook_events', function (Blueprint $table): void {
            $table->string('event_id', 128)->primary();
            $table->string('event_type', 80);
            $table->char('payload_sha256', 64);
            $table->uuid('payment_attempt_id')->nullable();
            $table->timestampTz('processed_at');
            $table->timestamps();

            $table->foreign('payment_attempt_id')->references('id')->on('razorpay_payment_attempts')->nullOnDelete();
            $table->index(['event_type', 'processed_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('razorpay_webhook_events');
        Schema::dropIfExists('razorpay_payment_attempts');
    }
};
