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
        // Separate external identities; never alter existing mail sender keys.
        Schema::create('kmj_mail_external_inbox', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('mailbox_user_id')->constrained('users')->restrictOnDelete();
            $table->uuid('event_id')->unique();
            $table->string('sender_email', 254);
            $table->string('recipient_email', 254);
            $table->string('subject', 180);
            $table->text('body');
            $table->timestamp('read_at')->nullable();
            $table->timestamps();
            $table->index(['mailbox_user_id', 'id']);
        });
    }

    public function down(): void
    {
        if (DB::table('kmj_mail_external_inbox')->exists()) {
            throw new RuntimeException('External Inbox is not empty; preserve it before rollback.');
        }

        Schema::dropIfExists('kmj_mail_external_inbox');
    }
};
