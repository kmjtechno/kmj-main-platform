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
        Schema::create('kmj_native_smtp_settings', function (Blueprint $table): void {
            $table->unsignedTinyInteger('id')->primary();
            $table->string('active_profile', 24)->default('loopback');
            $table->string('tested_profile', 24)->nullable();
            $table->string('tested_fingerprint', 64)->nullable();
            $table->unsignedBigInteger('tested_by')->nullable();
            $table->timestamp('tested_at')->nullable();
            $table->timestamps();
        });

        Schema::table('kmj_mail_messages', function (Blueprint $table): void {
            $table->string('native_smtp_profile', 24)->nullable();
        });
    }

    public function down(): void
    {
        if (DB::table('kmj_native_smtp_settings')->where('active_profile', '!=', 'loopback')->exists()
            || DB::table('kmj_mail_messages')->whereNotNull('native_smtp_profile')
                ->where('native_smtp_profile', '!=', 'loopback')->whereIn('delivery_state', ['queued', 'submitting'])->exists()) {
            throw new RuntimeException('Restore the default route and reconcile outstanding SMTP submissions before schema rollback.');
        }

        Schema::table('kmj_mail_messages', function (Blueprint $table): void {
            $table->dropColumn('native_smtp_profile');
        });
        Schema::dropIfExists('kmj_native_smtp_settings');
    }
};
