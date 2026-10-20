<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_project_onboarding_requests', function (Blueprint $table): void {
            $table->bigIncrements('id');
            $table->string('tenant_id', 64);
            $table->string('project_id', 64);
            $table->string('repository', 255);
            $table->string('host', 32);
            $table->string('status', 32)->default('awaiting_agent_pairing');
            $table->foreignId('requested_by')->constrained('users');
            $table->timestampsTz();
            $table->unique(['tenant_id', 'project_id'], 'cb_project_onboarding_tenant_project_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_project_onboarding_requests');
    }
};
