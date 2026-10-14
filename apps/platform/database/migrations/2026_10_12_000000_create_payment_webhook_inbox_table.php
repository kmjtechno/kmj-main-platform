<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('payment_webhook_inbox', function (Blueprint $table): void {
            $table->bigIncrements('id');
            $table->string('provider', 24);
            $table->char('merchant_identity_hash', 64);
            $table->string('environment', 8);
            $table->char('event_key', 64);
            $table->char('body_sha256', 64);
            $table->string('event_type', 64);
            $table->string('order_reference', 128);
            $table->string('payment_reference', 128);
            $table->string('state', 32)->default('received_unreconciled');
            $table->timestampsTz();

            $table->unique(
                ['provider', 'merchant_identity_hash', 'environment', 'event_key'],
                'payment_webhook_inbox_identity_unique',
            );
            $table->index(['provider', 'environment', 'created_at'], 'payment_webhook_inbox_activity_index');
            $table->index(['order_reference', 'state'], 'payment_webhook_inbox_order_index');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('payment_webhook_inbox');
    }
};
