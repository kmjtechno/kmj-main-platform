<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_model_evidence', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->uuid('ai_provider_id');
            $table->string('model_id', 128);
            // Owner-entered, current, explicit zero-price evidence (ADR-004). Never inferred.
            $table->string('price_evidence_url', 255);
            $table->string('price_evidence_note', 280);
            $table->timestamp('verified_at');
            $table->timestamp('expires_at');
            // 'no-training-documented' or 'unknown'. Unknown never qualifies for private source.
            $table->string('data_handling', 24)->default('unknown');
            $table->json('capabilities')->nullable();
            $table->unsignedInteger('context_limit')->nullable();
            $table->unsignedBigInteger('verified_by')->nullable();
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();

            $table->unique(['ai_provider_id', 'model_id']);
            $table->index('organization_id');
            $table->foreign('ai_provider_id')->references('id')->on('ai_providers')->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_model_evidence');
    }
};
