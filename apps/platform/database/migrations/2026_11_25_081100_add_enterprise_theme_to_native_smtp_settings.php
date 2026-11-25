<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('kmj_native_smtp_settings', function (Blueprint $table): void {
            $table->string('enterprise_theme', 32)->default('signature-red');
        });
    }

    public function down(): void
    {
        Schema::table('kmj_native_smtp_settings', function (Blueprint $table): void {
            $table->dropColumn('enterprise_theme');
        });
    }
};
