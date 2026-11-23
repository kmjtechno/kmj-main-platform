<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Source-only audit foundation. Every currently implemented entry
        // records a PENDING evidence request with ZERO credits. This table
        // neither verifies settlement nor authorizes issuance or redemption.
        Schema::create('kslp_reseller_credit_ledger', function (Blueprint $table): void {
            $table->bigIncrements('sequence');
            $table->uuid('issuer_organization_id');
            $table->uuid('licensed_product_id');
            $table->uuid('commercial_order_id');
            $table->char('event_key_hash', 64)->unique();
            $table->string('event_type', 32);
            $table->bigInteger('credits_delta');
            $table->string('evidence_state', 24);
            $table->unsignedBigInteger('actor_user_id');
            $table->timestampTz('created_at')->useCurrent();

            $table->foreign('issuer_organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('licensed_product_id')->references('id')->on('kslp_licensed_products')->restrictOnDelete();
            $table->foreign('commercial_order_id')->references('id')->on('commerce_orders')->restrictOnDelete();
            $table->foreign('actor_user_id')->references('id')->on('users')->restrictOnDelete();

            $table->unique(
                ['issuer_organization_id', 'licensed_product_id', 'commercial_order_id', 'event_type'],
                'kslp_reseller_evidence_once_per_order'
            );
            $table->index(
                ['issuer_organization_id', 'licensed_product_id', 'sequence'],
                'kslp_reseller_credit_scope'
            );
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('kslp_reseller_credit_ledger');
    }
};
