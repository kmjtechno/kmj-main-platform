<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_shared_quota_reservations', function (Blueprint $table): void {
            // Deliberately independent of provider and organization foreign keys.
            // Only opaque attempt IDs, a fixed quota scope and time are retained.
            $table->uuid('id')->primary();
            $table->string('scope', 32);
            $table->timestamp('created_at');
            $table->index(['scope', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_shared_quota_reservations');
    }
};
