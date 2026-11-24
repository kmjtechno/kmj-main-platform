<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Only scoped REVIEW authority. Never a credit or issuance grant.
        Schema::create('kslp_reseller_review_grants', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('issuer_organization_id');
            $table->uuid('licensed_product_id');
            $table->unsignedBigInteger('reseller_user_id');
            // Pin the current membership identity. Leaving/rejoining an
            // organization must not restore access from an old grant.
            $table->uuid('membership_id');
            $table->string('permission', 32);
            $table->timestampTz('expires_at');
            $table->timestampTz('revoked_at')->nullable();
            $table->unsignedBigInteger('granted_by_user_id');
            $table->timestampsTz();

            $table->foreign('issuer_organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('licensed_product_id')->references('id')->on('kslp_licensed_products')->restrictOnDelete();
            $table->foreign('reseller_user_id')->references('id')->on('users')->restrictOnDelete();
            $table->foreign('granted_by_user_id')->references('id')->on('users')->restrictOnDelete();
            $table->unique(
                ['issuer_organization_id', 'licensed_product_id', 'reseller_user_id'],
                'kslp_reseller_review_scope_unique'
            );
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('kslp_reseller_review_grants');
    }
};
