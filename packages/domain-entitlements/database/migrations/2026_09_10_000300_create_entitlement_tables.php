<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('entitlement_policies', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('product_id');
            $table->string('code', 96)->unique();
            $table->string('capability', 96);
            $table->string('status', 24)->default('active');
            $table->timestamps();

            $table->foreign('product_id')->references('id')->on('products')->restrictOnDelete();
            $table->index(['product_id', 'status']);
        });

        Schema::create('entitlements', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->uuid('product_id');
            $table->uuid('policy_id');
            $table->string('capability', 96);
            $table->string('status', 24)->default('active');
            $table->string('idempotency_key', 160)->unique();
            $table->timestampTz('starts_at');
            $table->timestampTz('ends_at')->nullable();
            $table->timestamps();

            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('product_id')->references('id')->on('products')->restrictOnDelete();
            $table->foreign('policy_id')->references('id')->on('entitlement_policies')->restrictOnDelete();
            $table->index(['organization_id', 'product_id', 'status']);
            $table->index(['organization_id', 'capability', 'status']);
        });

        Schema::create('entitlement_ledger', function (Blueprint $table): void {
            $table->bigIncrements('sequence');
            $table->uuid('entitlement_id');
            $table->uuid('organization_id');
            $table->string('event_type', 64);
            $table->json('payload');
            $table->timestampTz('occurred_at');
            $table->timestampTz('created_at')->useCurrent();

            $table->foreign('entitlement_id')->references('id')->on('entitlements')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->index(['organization_id', 'sequence']);
            $table->index(['entitlement_id', 'sequence']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('entitlement_ledger');
        Schema::dropIfExists('entitlements');
        Schema::dropIfExists('entitlement_policies');
    }
};
