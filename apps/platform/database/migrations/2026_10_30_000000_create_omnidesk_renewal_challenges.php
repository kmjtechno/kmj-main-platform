<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('omnidesk_renewal_challenges', function (Blueprint $table): void {
            // Only one current server challenge per activation. Reissuing
            // rotates it and invalidates any earlier unconsumed challenge.
            $table->uuid('activation_id')->primary();
            $table->char('challenge_sha256', 64);
            $table->timestamp('expires_at');
            $table->timestamp('consumed_at')->nullable();
            $table->timestamps();

            $table->foreign('activation_id')
                ->references('activation_id')->on('omnidesk_activation_bindings')
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('omnidesk_renewal_challenges');
    }
};
