<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * ADR-004 revision 2: evidence may describe a credit-limited model. Credit-limited evidence carries a KMJ-side
 * daily request cap and the owner's hard-cap attestation. The pairing is enforced by request validation and
 * the gateway fails closed on a missing or zero cap; no raw DDL is used here (migration review policy).
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
    }

    public function down(): void
    {
        Schema::table('ai_model_evidence', function (Blueprint $table): void {
            $table->dropColumn(['cost_class', 'credit_daily_cap', 'credit_hard_cap_attested_at']);
        });
    }
};
