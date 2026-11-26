<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Append-only record of refunds the owner made OUTSIDE this code (provider dashboard).
        // No row here moves money, calls a provider, or changes an order or license.
        Schema::create('commerce_order_refund_records', function (Blueprint $table): void {
            $table->id();
            $table->uuid('order_id');
            $table->uuid('organization_id');
            $table->unsignedBigInteger('amount_minor');
            $table->char('currency', 3);
            $table->string('provider_refund_reference', 120)->nullable();
            $table->string('reason', 240);
            $table->unsignedBigInteger('recorded_by_user_id')->nullable();
            $table->string('request_key', 120)->unique();
            $table->timestampTz('recorded_at');

            $table->foreign('order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('recorded_by_user_id')->references('id')->on('users')->nullOnDelete();
            $table->index(['order_id', 'id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('commerce_order_refund_records');
    }
};
