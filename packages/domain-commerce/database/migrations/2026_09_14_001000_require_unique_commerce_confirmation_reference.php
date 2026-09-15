<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('commerce_orders', function (Blueprint $table): void {
            $table->unique('confirmation_reference', 'commerce_orders_confirmation_reference_unique');
        });
    }

    public function down(): void
    {
        Schema::table('commerce_orders', function (Blueprint $table): void {
            $table->dropUnique('commerce_orders_confirmation_reference_unique');
        });
    }
};
