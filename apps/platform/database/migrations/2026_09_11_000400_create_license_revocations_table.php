<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('license_revocations', function (Blueprint $table): void {
            $table->id();
            $table->uuid('jti')->unique();
            $table->string('reason')->nullable();
            $table->timestamp('revoked_at');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('license_revocations');
    }
};
