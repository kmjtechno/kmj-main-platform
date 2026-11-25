<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Empty source-only projection. Only a future reviewed commercial
        // fulfillment authority may populate it, after verified settlement.
        Schema::create('codebridge_hosted_team_capacity', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->foreignUuid('commercial_order_id')->unique()->constrained('commerce_orders')->restrictOnDelete();
            $table->foreignUuid('entitlement_id')->unique()->constrained('entitlements')->restrictOnDelete();
            $table->foreignUuid('license_id')->unique()->constrained('kslp_licenses')->restrictOnDelete();
            $table->string('offer_version', 96);
            $table->unsignedInteger('seat_quantity');
            $table->unsignedBigInteger('total_minor');
            $table->char('currency', 3);
            $table->timestampTz('starts_at');
            $table->timestampTz('ends_at');
            $table->timestampTz('revoked_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_hosted_team_capacity');
    }
};
