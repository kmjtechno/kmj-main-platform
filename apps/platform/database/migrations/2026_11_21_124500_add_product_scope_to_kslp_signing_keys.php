<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('kslp_signing_keys', function (Blueprint $table): void {
            // Legacy generic KSLP keys stay unscoped. New OmniDesk signing
            // keys require an explicit product ID and finite validity.
            $table->string('product_id', 64)->nullable()->index();
        });
    }

    public function down(): void
    {
        // Dropping the product scope while ANY scoped key remains would
        // silently give generic KSLP/CloudOS clients visibility into that
        // product's issuer keys. Fail closed even for revoked keys: an owner
        // must first prove every scoped key is safely retired and removed.
        if (DB::table('kslp_signing_keys')->whereNotNull('product_id')->exists()) {
            throw new RuntimeException('KSLP_PRODUCT_SCOPE_ROLLBACK_BLOCKED');
        }

        Schema::table('kslp_signing_keys', function (Blueprint $table): void {
            $table->dropIndex(['product_id']);
            $table->dropColumn('product_id');
        });
    }
};
