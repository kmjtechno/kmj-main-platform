<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_model_tokens', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->string('name', 80);
            // SHA-256 of the token. The plain token is shown once at creation and is never stored.
            $table->string('token_hash', 64)->unique();
            $table->string('token_prefix', 16);
            // True = every call is treated as private source: only models with documented no-training evidence qualify.
            $table->boolean('private_source')->default(true);
            $table->unsignedBigInteger('created_by')->nullable();
            $table->timestamp('expires_at');
            $table->timestamp('last_used_at')->nullable();
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();

            $table->index(['organization_id', 'revoked_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_model_tokens');
    }
};
