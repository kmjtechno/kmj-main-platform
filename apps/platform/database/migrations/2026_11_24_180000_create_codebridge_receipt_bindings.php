<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_receipt_signers', function (Blueprint $table): void {
            $table->uuid('activation_id')->primary();
            $table->uuid('credential_id');
            $table->string('public_key', 44);
            $table->timestamps();
        });

        Schema::create('codebridge_receipt_bindings', function (Blueprint $table): void {
            $table->uuid('execution_id')->primary();
            $table->uuid('organization_id');
            $table->string('subject_key', 64);
            $table->string('plan_code', 24);
            $table->uuid('activation_id');
            $table->uuid('credential_id');
            $table->string('device_id', 64);
            $table->string('project_id', 64);
            $table->char('request_sha256', 64);
            $table->string('public_key', 44);
            $table->string('outcome', 16)->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_receipt_bindings');
        Schema::dropIfExists('codebridge_receipt_signers');
    }
};
