<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('codebridge_device_credentials', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->foreignUuid('license_id')->constrained('kslp_licenses');
            $table->foreignUuid('activation_id')->constrained('kslp_activations');
            $table->string('tenant_id', 64);
            $table->string('device_id', 64);
            $table->string('server_identity', 160);
            $table->char('token_hash', 64)->unique();
            $table->unsignedBigInteger('lease_sequence')->default(0);
            $table->unsignedBigInteger('expires_at_epoch');
            $table->timestamp('revoked_at')->nullable();
            $table->unique(['tenant_id', 'device_id']);
            $table->unique('activation_id');
        });
    }
    public function down(): void { Schema::dropIfExists('codebridge_device_credentials'); }
};
