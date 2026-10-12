<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('kslp_license_keys', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->uuid('licensed_product_id');
            $table->uuid('license_id')->unique();
            $table->char('key_digest', 64)->unique();
            $table->string('display_prefix', 16);
            $table->timestamp('first_activated_at')->nullable();
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();

            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('licensed_product_id')->references('id')->on('kslp_licensed_products')->restrictOnDelete();
            $table->foreign('license_id')->references('id')->on('kslp_licenses')->restrictOnDelete();
            $table->index(['organization_id', 'licensed_product_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('kslp_license_keys');
    }
};
