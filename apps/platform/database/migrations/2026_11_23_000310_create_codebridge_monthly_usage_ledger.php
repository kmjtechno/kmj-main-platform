<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Source-only: no gateway is wired to this ledger, and no hosted
        // customer quota, paid entitlement or checkout is activated.
        Schema::create('codebridge_usage_periods', function (Blueprint $table): void {
            $table->id();
            $table->uuid('organization_id');
            // This key must be derived by trusted KSLP authorization from the
            // account or paid seat, never from an MCP client parameter.
            $table->string('subject_key', 64);
            $table->date('period_start_utc');
            $table->string('plan_code', 24);
            $table->unsignedInteger('monthly_limit');
            $table->unsignedInteger('reserved_calls')->default(0);
            $table->unsignedInteger('completed_calls')->default(0);
            $table->timestamps();

            $table->unique(['organization_id', 'subject_key', 'period_start_utc'], 'cb_usage_period_unique');
            $table->index(['organization_id', 'period_start_utc'], 'cb_usage_period_org_month');
        });

        Schema::create('codebridge_usage_executions', function (Blueprint $table): void {
            $table->id();
            $table->uuid('organization_id');
            $table->string('subject_key', 64);
            $table->uuid('execution_id');
            $table->date('period_start_utc');
            // Reserved is not a billable completion; unknown delivery stays
            // reserved until separately authorized reconciliation.
            $table->string('state', 16);
            $table->timestamps();

            // A single remote execution cannot be counted under another seat
            // or in a later month by replaying its ID.
            $table->unique(['organization_id', 'execution_id'], 'cb_usage_execution_unique');
            $table->index(['organization_id', 'subject_key', 'period_start_utc'], 'cb_usage_execution_subject');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_usage_executions');
        Schema::dropIfExists('codebridge_usage_periods');
    }
};
