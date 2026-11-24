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
        // An Internet sender is not a KMJ user. Keep the existing foreign key.
        Schema::table('kmj_mail_messages', function (Blueprint $table): void {
            $table->foreignId('sender_user_id')->nullable()->change();
        });
    }

    public function down(): void
    {
        if (DB::table('kmj_mail_messages')->whereNull('sender_user_id')->exists()) {
            throw new RuntimeException('External inbound mail exists; preserve it before rollback.');
        }

        Schema::table('kmj_mail_messages', function (Blueprint $table): void {
            $table->foreignId('sender_user_id')->nullable(false)->change();
        });
    }
};
