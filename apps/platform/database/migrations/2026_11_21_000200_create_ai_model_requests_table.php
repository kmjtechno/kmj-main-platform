<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_model_requests', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->uuid('ai_provider_id');
            $table->string('model_id', 128);
            $table->string('outcome', 8);
            // Short machine code only. Prompts, responses and keys are never stored here.
            $table->string('error_code', 48)->nullable();
            $table->unsignedInteger('latency_ms')->default(0);
            $table->timestamp('created_at')->useCurrent();

            $table->index(['organization_id', 'created_at']);
            $table->index(['ai_provider_id', 'created_at']);
            $table->foreign('ai_provider_id')->references('id')->on('ai_providers')->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_model_requests');
    }
};
