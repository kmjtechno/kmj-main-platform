<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('knowledge_observations', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->string('project_key', 64);
            $table->string('topic_key', 96);
            $table->string('type', 24);
            $table->string('title', 160);
            $table->text('content');
            $table->char('content_sha256', 64);
            $table->unsignedInteger('revision');
            $table->timestamps();

            $table->foreign('organization_id')->references('id')->on('organizations')->cascadeOnDelete();
            $table->unique(['organization_id', 'project_key', 'topic_key'], 'knowledge_topic_per_project_unique');
            $table->index(['organization_id', 'project_key', 'updated_at'], 'knowledge_project_recent_idx');
        });

        Schema::create('knowledge_write_receipts', function (Blueprint $table): void {
            $table->id();
            $table->uuid('organization_id');
            $table->string('project_key', 64);
            $table->string('operation_id', 96);
            $table->char('request_sha256', 64);
            $table->uuid('observation_id')->nullable();
            $table->unsignedInteger('revision')->nullable();
            $table->timestamps();

            $table->foreign('organization_id')->references('id')->on('organizations')->cascadeOnDelete();
            $table->unique(['organization_id', 'project_key', 'operation_id'], 'knowledge_operation_per_project_unique');
        });

        // PostgreSQL-only full-text index; CI's in-memory SQLite takes a
        // conservative non-FTS read path, not an artificial pgvector dependency.
        if (DB::getDriverName() === 'pgsql') {
            DB::statement("CREATE INDEX knowledge_observations_search_gin ON knowledge_observations USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')))");
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('knowledge_write_receipts');
        Schema::dropIfExists('knowledge_observations');
    }
};
