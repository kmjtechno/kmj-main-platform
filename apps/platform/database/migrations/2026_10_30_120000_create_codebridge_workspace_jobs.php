<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_workspace_jobs', function (Blueprint $table): void {
            $table->ulid('id')->primary();
            $table->string('tenant_id', 64);
            $table->string('device_id', 64);
            $table->string('project_id', 64);
            $table->unsignedBigInteger('user_id');
            $table->string('tool', 40);
            $table->json('arguments');
            $table->string('idempotency_key', 64);
            // queued -> claimed -> running -> succeeded|failed ; cancelled|expired are terminal too.
            $table->string('status', 16)->default('queued');
            $table->unsignedTinyInteger('progress')->nullable();
            $table->char('claim_hash', 64)->nullable();
            $table->timestamp('claimed_at')->nullable();
            $table->timestamp('lease_expires_at')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->string('error_code', 64)->nullable();
            $table->string('summary', 2000)->nullable();
            $table->json('evidence')->nullable();
            $table->timestamps();

            $table->unique(['tenant_id', 'user_id', 'idempotency_key']);
            $table->index(['tenant_id', 'device_id', 'status', 'created_at']);
            $table->index(['tenant_id', 'project_id', 'created_at']);
        });

        Schema::create('codebridge_workspace_job_events', function (Blueprint $table): void {
            $table->id();
            $table->ulid('job_id');
            $table->unsignedInteger('seq');
            $table->string('kind', 24);
            $table->string('detail', 500)->nullable();
            $table->timestamp('created_at')->useCurrent();

            $table->foreign('job_id')->references('id')->on('codebridge_workspace_jobs')->cascadeOnDelete();
            $table->unique(['job_id', 'seq']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_workspace_job_events');
        Schema::dropIfExists('codebridge_workspace_jobs');
    }
};
