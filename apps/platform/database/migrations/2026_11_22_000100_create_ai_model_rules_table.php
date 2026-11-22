<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_model_rules', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('organization_id');
            $table->uuid('ai_provider_id');
            // Owner-attested pattern (literal prefix plus * wildcards) over one provider's discovered model ids.
            $table->string('model_pattern', 96);
            $table->string('price_evidence_url', 255);
            $table->string('price_evidence_note', 280);
            $table->string('data_handling', 24)->default('unknown');
            $table->json('capabilities')->nullable();
            $table->unsignedBigInteger('attested_by');
            $table->timestamp('attested_at');
            $table->timestamp('expires_at');
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();

            $table->unique(['ai_provider_id', 'model_pattern']);
            $table->index('organization_id');
            $table->foreign('ai_provider_id')->references('id')->on('ai_providers')->cascadeOnDelete();
        });

        Schema::table('ai_model_evidence', function (Blueprint $table): void {
            // Set only when a rule created the evidence, so revoking the rule revokes exactly its models.
            $table->uuid('ai_model_rule_id')->nullable()->after('ai_provider_id');
            $table->index('ai_model_rule_id');
        });
    }

    public function down(): void
    {
        Schema::table('ai_model_evidence', function (Blueprint $table): void {
            $table->dropIndex(['ai_model_rule_id']);
            $table->dropColumn('ai_model_rule_id');
        });
        Schema::dropIfExists('ai_model_rules');
    }
};
