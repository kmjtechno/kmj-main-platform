<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('omnidesk_activation_pairings', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('device_code_hash', 64)->unique();
            $table->string('user_code_hash', 64)->unique();
            $table->string('device_public_key', 43);
            $table->string('device_public_key_fingerprint', 71);
            $table->string('installation_id', 256);
            $table->string('platform', 32);
            $table->string('arch', 32);
            $table->string('client_version', 64);
            $table->string('code_challenge', 128);
            $table->string('status', 24)->default('pending');
            $table->uuid('organization_id')->nullable();
            $table->uuid('entitlement_id')->nullable();
            $table->timestamp('expires_at');
            $table->timestamp('approved_at')->nullable();
            $table->timestamp('consumed_at')->nullable();
            $table->timestamps();

            $table->index(['status', 'expires_at']);
            $table->index(['organization_id', 'device_public_key_fingerprint']);
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('entitlement_id')->references('id')->on('entitlements')->restrictOnDelete();
        });

        Schema::create('omnidesk_activation_grants', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('pairing_id')->unique();
            $table->string('token_hash', 64)->unique();
            $table->uuid('organization_id');
            $table->uuid('entitlement_id');
            $table->string('device_public_key', 43);
            $table->string('device_public_key_fingerprint', 71);
            $table->string('installation_id', 256);
            $table->timestamp('expires_at');
            $table->timestamp('consumed_at')->nullable();
            $table->timestamps();

            $table->index(['organization_id', 'expires_at']);
            $table->foreign('pairing_id')->references('id')->on('omnidesk_activation_pairings')->restrictOnDelete();
            $table->foreign('organization_id')->references('id')->on('organizations')->restrictOnDelete();
            $table->foreign('entitlement_id')->references('id')->on('entitlements')->restrictOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('omnidesk_activation_grants');
        Schema::dropIfExists('omnidesk_activation_pairings');
    }
};
