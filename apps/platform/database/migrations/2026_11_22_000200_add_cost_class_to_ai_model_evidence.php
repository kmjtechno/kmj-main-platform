<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * ADR-004 revision 2: evidence may describe a credit-limited model. Credit-limited evidence always carries
 * a KMJ-side daily request cap and the owner's hard-cap attestation; the database enforces that pairing.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('ai_model_evidence', function (Blueprint $table): void {
            $table->string('cost_class', 16)->default('free');
            $table->unsignedInteger('credit_daily_cap')->nullable();
            $table->timestamp('credit_hard_cap_attested_at')->nullable();
        });

        if (DB::getDriverName() === 'pgsql') {
            DB::statement("ALTER TABLE ai_model_evidence ADD CONSTRAINT ai_model_evidence_cost_class_chk CHECK (cost_class IN ('free', 'credit-limited') AND (cost_class = 'free' OR (credit_daily_cap IS NOT NULL AND credit_daily_cap > 0 AND credit_hard_cap_attested_at IS NOT NULL)))");
        }
    }

    public function down(): void
    {
        if (DB::getDriverName() === 'pgsql') {
            DB::statement('ALTER TABLE ai_model_evidence DROP CONSTRAINT IF EXISTS ai_model_evidence_cost_class_chk');
        }
        Schema::table('ai_model_evidence', function (Blueprint $table): void {
            $table->dropColumn(['cost_class', 'credit_daily_cap', 'credit_hard_cap_attested_at']);
        });
    }
};
