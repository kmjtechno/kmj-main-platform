<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('codebridge_receipt_bindings', function (Blueprint $table): void {
            $table->string('verified_signature', 88)->nullable();
            $table->boolean('pilot_only')->default(false);
        });
    }

    public function down(): void
    {
        Schema::table('codebridge_receipt_bindings', function (Blueprint $table): void {
            $table->dropColumn(['verified_signature', 'pilot_only']);
        });
    }
};
