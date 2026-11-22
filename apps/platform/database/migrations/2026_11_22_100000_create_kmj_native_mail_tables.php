<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Internal KMJ staff authorization is distinct from customer organization membership.
        Schema::create('kmj_mail_staff', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('user_id')->unique()->constrained('users')->restrictOnDelete();
            $table->foreignId('granted_by_user_id')->constrained('users')->restrictOnDelete();
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();
        });

        // Each owner/staff mailbox stores its own independent copy.
        // No external recipient addresses, OAuth tokens, SMTP credentials or MIME attachments.
        Schema::create('kmj_mail_messages', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('mailbox_user_id')->constrained('users')->restrictOnDelete();
            $table->foreignId('sender_user_id')->constrained('users')->restrictOnDelete();
            $table->foreignId('recipient_user_id')->nullable()->constrained('users')->restrictOnDelete();
            $table->uuid('thread_id');
            $table->string('folder', 12);
            $table->string('previous_folder', 12)->nullable();
            $table->string('subject', 180);
            $table->text('body');
            $table->uuid('client_key')->nullable();
            $table->timestamp('read_at')->nullable();
            $table->timestamp('sent_at')->nullable();
            $table->timestamps();

            $table->unique(['mailbox_user_id', 'client_key']);
            $table->index(['mailbox_user_id', 'folder', 'id']);
            $table->index(['mailbox_user_id', 'thread_id', 'id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('kmj_mail_messages');
        Schema::dropIfExists('kmj_mail_staff');
    }
};
