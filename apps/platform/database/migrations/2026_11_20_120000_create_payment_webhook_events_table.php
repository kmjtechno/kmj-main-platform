<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Append-only inbox of signature-verified provider notifications.
        // Deliberately stores no raw payload: customer contact data stays at the provider.
        Schema::create('payment_webhook_events', function (Blueprint $table): void {
            $table->id();
            $table->string('provider', 24);
            $table->string('event_id', 160);
            $table->string('event_type', 96)->nullable();
            $table->string('provider_order_id', 64)->nullable();
            $table->string('provider_payment_id', 64)->nullable();
            $table->char('payload_sha256', 64);
            // Verified receipt is not settlement: reconciliation is a separate, later step.
            $table->string('processing_status', 24)->default('received');
            $table->timestampTz('received_at');
            $table->timestampsTz();

            $table->unique(['provider', 'event_id']);
            $table->index(['provider', 'provider_order_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('payment_webhook_events');
    }
};
