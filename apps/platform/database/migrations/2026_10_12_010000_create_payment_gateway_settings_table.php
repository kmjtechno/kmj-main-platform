<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('payment_gateway_settings', function (Blueprint $table): void {
            $table->string('provider', 24)->primary();
            $table->string('environment', 16)->default('sandbox');
            $table->string('merchant_status', 32)->default('not_verified');
            $table->boolean('international_requested')->default(false);
            $table->text('encrypted_client_id')->nullable();
            $table->text('encrypted_client_secret')->nullable();
            $table->text('encrypted_webhook_secret')->nullable();
            $table->foreignId('updated_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestampsTz();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('payment_gateway_settings');
    }
};
