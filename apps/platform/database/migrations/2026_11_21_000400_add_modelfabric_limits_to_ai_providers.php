<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('ai_providers', function (Blueprint $table): void {
            // Lower number = preferred when task fit is equal. 100 is neutral.
            $table->unsignedSmallInteger('priority')->default(100);
            // Owner-set cap on routed attempts per UTC day; null = no owner cap (provider limits still apply).
            $table->unsignedInteger('daily_request_cap')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('ai_providers', function (Blueprint $table): void {
            $table->dropColumn(['priority', 'daily_request_cap']);
        });
    }
};
