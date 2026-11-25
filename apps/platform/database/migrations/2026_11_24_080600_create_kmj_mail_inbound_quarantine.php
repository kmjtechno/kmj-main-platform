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
        Schema::create('kmj_mail_inbound_quarantine', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('mailbox_user_id')->constrained('users')->restrictOnDelete();
            $table->uuid('event_id')->unique();
            $table->string('recipient', 254);
            $table->string('raw_sha256', 64);
            $table->unsignedInteger('raw_bytes');
            $table->text('encrypted_envelope_sender');
            $table->longText('encrypted_mime');
            $table->timestamp('received_at');
            $table->unique(['mailbox_user_id', 'recipient', 'raw_sha256'], 'kmj_mail_inbound_dedupe');
            $table->index(['mailbox_user_id', 'received_at']);
        });
    }

    public function down(): void
    {
        // Never destroy actual received mail during a rollback.
        if (DB::table('kmj_mail_inbound_quarantine')->exists()) {
            throw new RuntimeException('Inbound quarantine is not empty; preserve it before rollback.');
        }

        Schema::dropIfExists('kmj_mail_inbound_quarantine');
    }
};
