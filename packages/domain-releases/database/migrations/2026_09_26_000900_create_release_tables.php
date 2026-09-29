<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('product_releases', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('product_id');
            $table->string('version', 96);
            $table->string('artifact_digest', 71);
            $table->string('provenance_ref', 512);
            $table->string('status', 24)->default('staged');
            $table->timestampTz('promoted_at')->nullable();
            $table->timestampTz('revoked_at')->nullable();
            $table->timestamps();

            $table->foreign('product_id')
                ->references('id')->on('products')->restrictOnDelete();
            $table->unique(['product_id', 'version']);
            $table->index(['product_id', 'status', 'promoted_at']);
        });

        Schema::create('release_artifacts', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('release_id')->unique();
            $table->string('filename', 255);
            $table->string('disk', 64)->default('local');
            $table->string('path', 1024);
            $table->string('media_type', 160)->nullable();
            $table->unsignedBigInteger('size_bytes')->nullable();
            $table->string('digest', 71);
            $table->timestamps();

            $table->foreign('release_id')
                ->references('id')->on('product_releases')->cascadeOnDelete();
            $table->index('digest');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('release_artifacts');
        Schema::dropIfExists('product_releases');
    }
};
