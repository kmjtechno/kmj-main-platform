<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Empty registry only. Commercial settlement must populate it through
        // a separately reviewed authority; no device or trial grants a seat.
        Schema::create('codebridge_hosted_seat_assignments', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->foreignUuid('organization_id')->constrained('organizations')->restrictOnDelete();
            $table->foreignUuid('membership_id')->constrained('organization_memberships')->restrictOnDelete();
            $table->foreignUuid('license_id')->constrained('kslp_licenses')->restrictOnDelete();
            $table->unsignedInteger('assignment_revision');
            $table->timestampTz('starts_at');
            $table->timestampTz('ends_at');
            $table->timestampTz('revoked_at')->nullable();
            $table->timestamps();

            $table->unique(['license_id', 'membership_id'], 'cb_seat_license_member_unique');
            $table->index(['organization_id', 'membership_id'], 'cb_seat_org_member');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_hosted_seat_assignments');
    }
};
