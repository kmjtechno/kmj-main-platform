<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_oauth_clients', function (Blueprint $table): void {
            $table->string('client_id', 64)->primary();
            $table->string('client_name', 120);
            $table->json('redirect_uris');
            $table->timestamps();
        });

        Schema::create('codebridge_oauth_codes', function (Blueprint $table): void {
            $table->string('code_hash', 64)->primary();
            $table->string('client_id', 64);
            $table->unsignedBigInteger('user_id');
            $table->string('redirect_uri', 512);
            $table->string('code_challenge', 43);
            $table->string('scope', 512);
            $table->string('resource', 512);
            $table->unsignedBigInteger('expires_at_epoch');
            $table->unsignedBigInteger('consumed_at_epoch')->nullable();
            $table->timestamps();

            $table->foreign('client_id')->references('client_id')->on('codebridge_oauth_clients')->cascadeOnDelete();
            $table->foreign('user_id')->references('id')->on('users')->cascadeOnDelete();
        });

        Schema::create('codebridge_oauth_refresh_tokens', function (Blueprint $table): void {
            $table->string('token_hash', 64)->primary();
            $table->uuid('family_id');
            $table->string('client_id', 64);
            $table->unsignedBigInteger('user_id');
            $table->string('scope', 512);
            $table->string('resource', 512);
            $table->unsignedBigInteger('expires_at_epoch');
            $table->unsignedBigInteger('rotated_at_epoch')->nullable();
            $table->unsignedBigInteger('revoked_at_epoch')->nullable();
            $table->timestamps();

            $table->index('family_id');
            $table->foreign('client_id')->references('client_id')->on('codebridge_oauth_clients')->cascadeOnDelete();
            $table->foreign('user_id')->references('id')->on('users')->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_oauth_refresh_tokens');
        Schema::dropIfExists('codebridge_oauth_codes');
        Schema::dropIfExists('codebridge_oauth_clients');
    }
};
