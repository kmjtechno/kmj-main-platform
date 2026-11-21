<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
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
        Schema::table('kslp_signing_keys', function (Blueprint $table): void {
            $table->dropIndex(['product_id']);
            $table->dropColumn('product_id');
        });
    }
};
