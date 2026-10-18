<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_project_assignments', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('tenant_id', 64);
            $table->string('device_id', 64);
            $table->string('project_id', 64);
            $table->string('project_name', 100);
            $table->string('repository_url', 255);
            // A dashboard request does NOT expand the agent's allowed local roots,
            // issue a device credential, or prove a CodeBridge heartbeat.
            $table->string('status', 32)->default('pending_local_setup');
            $table->unsignedBigInteger('requested_by');
            $table->timestamps();
            $table->unique(['tenant_id', 'device_id', 'project_id'], 'cb_assign_tenant_device_project_unique');
            $table->index(['tenant_id', 'device_id', 'status'], 'cb_assign_tenant_device_status_idx');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_project_assignments');
    }
};
