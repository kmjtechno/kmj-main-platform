<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('outbox_messages', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('event_type', 160)->index();
            $table->string('aggregate_type', 120);
            $table->string('aggregate_id', 191);
            $table->uuid('organization_id')->nullable()->index();
            $table->string('idempotency_key', 191)->unique();
            $table->json('payload');
            $table->timestamp('occurred_at')->index();
            $table->timestamp('published_at')->nullable()->index();
            $table->unsignedInteger('attempts')->default(0);
            $table->text('last_error')->nullable();
            $table->timestamps();

            $table->index(['aggregate_type', 'aggregate_id']);
        });

        Schema::create('outbox_consumptions', function (Blueprint $table): void {
            $table->id();
            $table->uuid('message_id');
            $table->string('consumer', 160);
            $table->timestamp('consumed_at');
            $table->timestamps();

            $table->unique(['message_id', 'consumer']);
            $table->foreign('message_id')
                ->references('id')
                ->on('outbox_messages')
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('outbox_consumptions');
        Schema::dropIfExists('outbox_messages');
    }
};
