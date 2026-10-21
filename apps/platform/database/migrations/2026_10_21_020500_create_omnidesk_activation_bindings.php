<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('omnidesk_activation_bindings', function (Blueprint $table): void {
            $table->uuid('activation_id')->primary();
            $table->uuid('entitlement_id');
            $table->uuid('organization_id');
            $table->string('device_public_key', 128);
            $table->string('device_public_key_fingerprint', 96);
            $table->string('installation_id', 256);
            $table->string('idempotency_key', 128)->unique();
            $table->string('current_jti', 128)->nullable();
            $table->unsignedBigInteger('current_sequence')->default(0);
            $table->timestamps();

            $table->foreign('activation_id')
                ->references('id')->on('kslp_activations')
                ->cascadeOnDelete();
            $table->foreign('entitlement_id')
                ->references('id')->on('entitlements')
                ->restrictOnDelete();
            $table->foreign('organization_id')
                ->references('id')->on('organizations')
                ->restrictOnDelete();
            $table->index(['organization_id', 'entitlement_id']);
            $table->index(['device_public_key_fingerprint', 'installation_id']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('omnidesk_activation_bindings');
    }
};
