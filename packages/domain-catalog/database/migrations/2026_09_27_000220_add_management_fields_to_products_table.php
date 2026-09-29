<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('products', function (Blueprint $table): void {
            $table->string('lifecycle', 32)->default('planned')->index();
            $table->boolean('is_public')->default(false)->index();
            $table->unsignedInteger('sort_order')->default(100)->index();
            $table->string('image_path', 255)->nullable();
            $table->text('summary')->nullable();
            $table->boolean('purchase_enabled')->default(false)->index();
            $table->boolean('licensing_enabled')->default(false)->index();
        });
    }

    public function down(): void
    {
        Schema::table('products', function (Blueprint $table): void {
            $table->dropColumn(['lifecycle', 'is_public', 'sort_order', 'image_path', 'summary', 'purchase_enabled', 'licensing_enabled']);
        });
    }
};
