<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_device_pairings', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('device_code_hash', 64)->unique();
            $table->string('user_code_hash', 64)->unique();
            $table->string('device_id', 64);
            $table->string('device_name', 128);
            $table->string('platform', 32);
            $table->string('arch', 32);
            $table->string('project_id', 64);
            $table->string('project_name', 128);
            $table->json('requested_permissions');
            $table->string('code_challenge', 128);
            $table->string('status', 24)->default('pending');
            $table->string('tenant_id', 64)->nullable();
            $table->uuid('license_id')->nullable();
            $table->uuid('activation_id')->nullable();
            $table->text('credential_ciphertext')->nullable();
            $table->timestamp('expires_at');
            $table->timestamp('approved_at')->nullable();
            $table->timestamp('consumed_at')->nullable();
            $table->timestamps();

            $table->index(['status', 'expires_at']);
            $table->index(['tenant_id', 'device_id']);
            $table->foreign('license_id')->references('id')->on('kslp_licenses')->restrictOnDelete();
            $table->foreign('activation_id')->references('id')->on('kslp_activations')->restrictOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_device_pairings');
    }
};
