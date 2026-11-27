<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Which product a customer signed up for. Not an entitlement or license.
        Schema::create('product_signups', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->string('product_slug', 96);
            $table->string('state', 24)->default('waiting');
            $table->timestamps();

            $table->unique(['user_id', 'product_slug']);
            $table->index(['product_slug', 'state']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('product_signups');
    }
};
