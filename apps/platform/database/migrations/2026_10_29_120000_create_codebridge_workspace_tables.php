<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Conversations belong to ONE tenant, ONE user and ONE project the tenant has paired.
        // They never hold device credentials, shell commands or provider keys.
        Schema::create('codebridge_workspace_conversations', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('tenant_id', 64);
            $table->string('device_id', 64);
            $table->string('project_id', 64);
            $table->unsignedBigInteger('user_id');
            $table->string('title', 120);
            $table->timestamps();
            $table->index(['tenant_id', 'user_id', 'device_id', 'project_id', 'updated_at'], 'cb_ws_conv_scope_idx');
        });

        Schema::create('codebridge_workspace_messages', function (Blueprint $table): void {
            // ULIDs sort by creation time (monotonic within a millisecond), which keeps transcript order exact.
            $table->ulid('id')->primary();
            $table->uuid('conversation_id');
            $table->string('role', 16); // user | assistant
            $table->text('content');
            $table->string('status', 16); // complete | running | failed | cancelled
            $table->string('provider_id', 64)->nullable();
            $table->string('model', 128)->nullable();
            $table->string('error_code', 64)->nullable();
            $table->ulid('retry_of')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
            $table->foreign('conversation_id')->references('id')->on('codebridge_workspace_conversations')->cascadeOnDelete();
            $table->index(['conversation_id', 'id'], 'cb_ws_msg_conv_idx');
        });

        // Durable record of what THIS application really did (inference lifecycle only).
        // Device job/tool events are not recorded here: they live on the paired device.
        Schema::create('codebridge_workspace_events', function (Blueprint $table): void {
            $table->id();
            $table->uuid('conversation_id');
            $table->ulid('message_id')->nullable();
            $table->string('kind', 32);
            $table->string('status', 16);
            $table->string('detail', 200)->nullable();
            $table->timestamp('created_at')->useCurrent();
            $table->foreign('conversation_id')->references('id')->on('codebridge_workspace_conversations')->cascadeOnDelete();
            $table->index(['conversation_id', 'id'], 'cb_ws_evt_conv_idx');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_workspace_events');
        Schema::dropIfExists('codebridge_workspace_messages');
        Schema::dropIfExists('codebridge_workspace_conversations');
    }
};
