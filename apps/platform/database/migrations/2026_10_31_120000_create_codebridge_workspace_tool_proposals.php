<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // A proposal is ONLY a stored, validated suggestion from an assistant message. It has no authority:
        // nothing is queued for a device until the same user explicitly confirms it, and confirmation
        // re-checks the paired project grant through the normal job pipeline.
        Schema::create('codebridge_workspace_tool_proposals', function (Blueprint $table): void {
            $table->ulid('id')->primary();
            $table->uuid('conversation_id');
            $table->ulid('message_id');
            $table->string('tenant_id', 64);
            $table->unsignedBigInteger('user_id');
            $table->string('device_id', 64);
            $table->string('project_id', 64);
            $table->string('tool', 40);
            $table->json('arguments');
            // pending -> confirmed | rejected | expired ; the first terminal state wins.
            $table->string('status', 16)->default('pending');
            $table->ulid('job_id')->nullable();
            $table->timestamp('decided_at')->nullable();
            $table->timestamps();

            $table->foreign('conversation_id')->references('id')->on('codebridge_workspace_conversations')->cascadeOnDelete();
            $table->unique('message_id');
            $table->index(['conversation_id', 'id'], 'cb_ws_prop_conv_idx');
            $table->index(['tenant_id', 'user_id', 'status'], 'cb_ws_prop_scope_idx');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_workspace_tool_proposals');
    }
};
