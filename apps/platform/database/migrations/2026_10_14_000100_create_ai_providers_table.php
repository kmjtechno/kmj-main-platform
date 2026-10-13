<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_providers', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->string('name', 80);
            $table->string('preset', 24);
            $table->string('kind', 24)->default('openai-compatible');
            $table->string('base_url', 255);
            // Laravel "encrypted" cast (AES-256 with APP_KEY). Never serialised to the client.
            $table->text('api_key');
            $table->string('key_last4', 4)->nullable();
            $table->boolean('enabled')->default(true);
            $table->boolean('free_only')->default(true);
            $table->string('default_model', 128)->nullable();
            $table->json('fallback_models')->nullable();
            $table->json('models_cache')->nullable();
            $table->timestamp('models_checked_at')->nullable();
            $table->string('health', 16)->default('unknown');
            $table->timestamp('health_checked_at')->nullable();
            $table->string('last_error_code', 48)->nullable();
            $table->json('rate_limit')->nullable();
            $table->unsignedBigInteger('created_by')->nullable();
            $table->timestamps();

            $table->unique(['organization_id', 'name']);
            $table->index('organization_id');
            $table->foreign('organization_id')->references('id')->on('organizations')->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_providers');
    }
};
