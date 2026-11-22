<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Additive-only: keep the existing private KMJ internal mailbox copies
        // and do not mutate the current Internet MX, Postfix or live email data.
        Schema::table('kmj_mail_messages', function (Blueprint $table): void {
            $table->string('recipient_email', 254)->nullable();
            $table->string('sender_email', 254)->nullable();
            $table->string('delivery_state', 24)->nullable();
            $table->string('delivery_error_code', 32)->nullable();
            $table->timestamp('transport_attempted_at')->nullable();
            $table->timestamp('transport_accepted_at')->nullable();
            $table->index(['mailbox_user_id', 'delivery_state', 'id'], 'kmj_mail_external_status_idx');
        });

        // A staff employee cannot impersonate another person's address or
        // auto-use the owner's company-wide info@ mailbox. Explicit owner grant.
        Schema::table('kmj_mail_staff', function (Blueprint $table): void {
            $table->string('sender_alias', 254)->nullable()->unique('kmj_mail_staff_sender_alias_unique');
        });
    }

    public function down(): void
    {
        Schema::table('kmj_mail_staff', function (Blueprint $table): void {
            $table->dropUnique('kmj_mail_staff_sender_alias_unique');
            $table->dropColumn('sender_alias');
        });

        Schema::table('kmj_mail_messages', function (Blueprint $table): void {
            $table->dropIndex('kmj_mail_external_status_idx');
            $table->dropColumn([
                'recipient_email', 'sender_email', 'delivery_state',
                'delivery_error_code', 'transport_attempted_at', 'transport_accepted_at',
            ]);
        });
    }
};
