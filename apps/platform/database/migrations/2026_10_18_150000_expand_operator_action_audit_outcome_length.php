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
        // Existing audit records and indexes remain in place. The original
        // VARCHAR(24) cannot hold 'sandbox_order_created_only' (26 chars).
        Schema::table('operator_action_audits', function (Blueprint $table): void {
            $table->string('outcome', 64)->change();
        });
    }

    public function down(): void
    {
        // A rollback must never silently truncate existing compliance
        // evidence, including payment sandbox probe audit outcomes.
        if (DB::table('operator_action_audits')
            ->whereRaw('char_length(outcome) > 24')
            ->exists()) {
            throw new RuntimeException('OPERATOR_AUDIT_OUTCOME_ROLLBACK_DATA_TOO_LONG');
        }

        Schema::table('operator_action_audits', function (Blueprint $table): void {
            $table->string('outcome', 24)->change();
        });
    }
};
